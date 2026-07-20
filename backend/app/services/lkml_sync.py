"""LKML 邮件同步服务：从 lore.kernel.org git 分片镜像读取邮件、解析、入库。

背景：
  lore.kernel.org 已启用 Anubis 反爬保护，旧的 HTTP mbox 接口（*.mbox）全部失效。
  官方推荐通过 git 分片镜像读取归档：
    https://lore.kernel.org/lkml/{0..N}
  每个分片是一个 ~1GB 的 bare git 仓库，每个 commit = 一封邮件。
  - commit 的 author/committer date = 邮件日期（public-inbox 设定）
  - commit 添加的 blob 文件内容 = 原始 RFC822 邮件（headers + body）
  - 分片 0 = 最旧（~1998），分片 N = 最新（当月）

  本模块负责：
  1. 探测最大分片编号（probe_max_shard）
  2. 克隆/fetch 最新分片到本地（fetch_shard / fetch_latest_shard）
  3. 用 git log 按日期范围提取 commit，批量读取 blob 解析为 email.message.Message
  4. 入库（按 message_id 去重）
  5. 计算 patch-id、识别子系统、统计回复数

  注意：批量历史月份的邮件可能在较旧分片中，需先运行
        scripts/download-lkml-mbox.sh 下载所需分片。
"""
from __future__ import annotations

import asyncio
import email as email_lib
import hashlib
import re
import shutil
import subprocess
from datetime import datetime, timezone
from email.message import Message
from email.utils import getaddresses, parsedate_to_datetime
from pathlib import Path
from typing import Iterator, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import async_session_factory
from app.models.email import Email

# ============ 子系统关键词 (简化的 MAINTAINERS 抽取) ============
_SUBSYSTEM_KEYWORDS: dict[str, list[str]] = {
    "sched": ["scheduler", "cfs", "rt ", "fair group", "load balance", "rq->"],
    "mm": ["page ", "vm ", "slab", "page_alloc", "mmap", "oom", "vmscan", "memcg"],
    "net": ["net:", "tcp", "udp", "socket", "skb", "ipv4", "ipv6", "netfilter"],
    "fs": ["vfs", "ext4", "xfs", "btrfs", "inode", "dentry", "superblock"],
    "block": ["block:", "blk-", "bio ", "request queue", "io scheduler", "nvme"],
    "drivers": ["driver", "pci", "usb", "i2c", "spi", "platform"],
    "arch": ["arch/", "x86", "arm64", "riscv", "powerpc"],
    "locking": ["spinlock", "mutex", "rcu", "rwlock"],
    "tracing": ["trace", "ftrace", "bpf", "perf "],
    "security": ["selinux", "apparmor", "smack", "seccomp", "lsm"],
}

# 性能相关关键词
_PERF_KEYWORDS = [
    "perf", "performance", "speedup", "optimization", "optimize",
    "throughput", "latency", "benchmark", "faster", "slow path",
    "hot path", "overhead", "scalability", "cache miss", "batch",
]


def detect_subsystem(subject: str, body: str | None) -> Optional[str]:
    """根据 subject 前缀 [PATCH xxx/yyy] 与正文关键词识别子系统。"""
    text = f"{subject}\n{body or ''}".lower()
    # 优先从 subject 抓取 [PATCH subsystem] 形式
    m = re.search(r"\[patch[^\]]*\b(sched|mm|net|fs|block|drivers|arch|locking|tracing|security)\b", text)
    if m:
        return m.group(1)
    # 否则按关键词计分
    best, best_score = None, 0
    for sub, kws in _SUBSYSTEM_KEYWORDS.items():
        score = sum(text.count(k) for k in kws)
        if score > best_score:
            best, best_score = sub, score
    return best if best_score > 0 else None


def is_performance_related(subject: str, body: str | None) -> bool:
    text = f"{subject}\n{body or ''}".lower()
    return any(kw in text for kw in _PERF_KEYWORDS)


def compute_patch_id(diff_text: str) -> str:
    """模拟 `git patch-id` 算法：对规范化后的 diff 求 SHA1。

    规范化规则（与 git patch-id 基本一致）：
    1. 去除行首/行尾空白
    2. 去除 index 行、@@ 行中的行号（保留文件名）
    3. 去除 diffstat
    """
    if not diff_text:
        return ""
    normalized_lines: list[str] = []
    for line in diff_text.splitlines():
        # 跳过空行
        if not line.strip():
            continue
        # 跳过 index 行
        if line.startswith("index ") or line.startswith("Index: "):
            continue
        # @@ -a,b +c,d @@ ... → @@ -a,b +c,d @@（去除行号偏移可选项；保留基本结构）
        if line.startswith("@@"):
            # 保留 @@ ... @@ 但去掉末尾的函数上下文
            m = re.match(r"^@@ -\d+(?:,\d+)? \+\d+(?:,\d+)? @@", line)
            if m:
                normalized_lines.append(m.group(0))
                continue
        # 普通行：去除行尾空白
        normalized_lines.append(line.rstrip())
    payload = "\n".join(normalized_lines).encode("utf-8")
    return hashlib.sha1(payload).hexdigest()


def _get_header(msg: Message, name: str) -> str:
    val = msg.get(name)
    if not val:
        return ""
    return str(val).strip()


def _parse_refs(refs_raw: str) -> list[str]:
    if not refs_raw:
        return []
    return [part.strip().strip("<>") for part in refs_raw.split() if part.strip()]


def _extract_body(msg: Message) -> str:
    """提取邮件正文（优先 text/plain）。"""
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            cdisp = part.get("Content-Disposition", "")
            if ctype == "text/plain" and "attachment" not in cdisp.lower():
                try:
                    return part.get_payload(decode=True).decode(
                        part.get_content_charset() or "utf-8", errors="replace"
                    )
                except Exception:  # noqa: BLE001
                    continue
        return ""
    try:
        payload = msg.get_payload(decode=True)
        if payload is None:
            return str(msg.get_payload())
        return payload.decode(msg.get_content_charset() or "utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        return str(msg.get_payload())


def parse_mbox(mbox_path: Path) -> Iterator[Message]:
    """用 mailbox.mbox 迭代解析旧的 mbox 文件（保留以兼容本地历史归档）。"""
    import mailbox
    mbox = mailbox.mbox(str(mbox_path))
    try:
        for msg in mbox:
            yield msg
    finally:
        mbox.close()


# ============ git 分片镜像操作 ============

def _shard_url(shard_num: int) -> str:
    return f"{settings.LKML_GIT_BASE.rstrip('/')}/{shard_num}"


def _shard_path(shard_num: int) -> Path:
    return settings.lkml_mirror_dir / f"lkml-{shard_num}.git"


async def _run_git(
    *args: str,
    cwd: Optional[Path] = None,
    timeout: int = 600,
) -> tuple[int, bytes, bytes]:
    """异步执行 git 命令。返回 (returncode, stdout, stderr)。"""
    proc = await asyncio.create_subprocess_exec(
        "git", *args,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return proc.returncode or 0, stdout, stderr
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        raise


async def shard_exists(shard_num: int) -> bool:
    """检测指定分片是否存在（用 git ls-remote 探测 HEAD）。"""
    try:
        rc, out, _ = await _run_git(
            "ls-remote", _shard_url(shard_num), "HEAD",
            timeout=settings.LKML_PROBE_TIMEOUT,
        )
        return rc == 0 and b"HEAD" in out
    except Exception:  # noqa: BLE001
        return False


async def probe_max_shard() -> int:
    """探测最大分片编号（分片 0=最旧，N=最新）。返回 N。

    采用「指数扩张 + 二分查找」组合策略，最多约 2*log2(N) 次网络请求。
    """
    # 1. 指数扩张找上界
    lo, hi = 0, 1
    if not await shard_exists(0):
        return -1  # 网络不通或源站异常
    while hi <= 1024:
        if await shard_exists(hi):
            lo = hi
            hi *= 2
        else:
            break
    # 2. 二分查找最大存在编号
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if await shard_exists(mid):
            lo = mid
        else:
            hi = mid - 1
    return lo


async def fetch_shard(shard_num: int, *, shallow: bool = False) -> Path:
    """克隆或增量 fetch 指定分片。返回本地 bare 仓库路径。

    - 不存在时：git clone --bare（shallow=True 用 --depth 1）
    - 已存在时：git fetch --all --prune
    """
    repo_path = _shard_path(shard_num)
    url = _shard_url(shard_num)
    settings.lkml_mirror_dir.mkdir(parents=True, exist_ok=True)

    if not repo_path.exists():
        args = ["clone", "--bare"]
        if shallow:
            args += ["--depth", "1"]
        args += [url, str(repo_path)]
        rc, _, err = await _run_git(*args, cwd=settings.lkml_mirror_dir, timeout=3600)
        if rc != 0:
            if repo_path.exists():
                shutil.rmtree(repo_path, ignore_errors=True)
            raise RuntimeError(
                f"git clone shard {shard_num} failed: {err.decode(errors='replace').strip()}"
            )
    else:
        rc, _, err = await _run_git(
            "--git-dir", str(repo_path), "fetch", "--all", "--prune",
            timeout=3600,
        )
        if rc != 0:
            raise RuntimeError(
                f"git fetch shard {shard_num} failed: {err.decode(errors='replace').strip()}"
            )
    return repo_path


async def fetch_latest_shard() -> tuple[int, Path]:
    """探测并 fetch 最新分片。返回 (分片编号, 路径)。"""
    max_shard = await probe_max_shard()
    if max_shard < 0:
        raise RuntimeError(
            "无法探测 lore.kernel.org 分片（网络不通或源站异常）。"
            "请检查网络或先运行 scripts/download-lkml-mbox.sh 手动下载。"
        )
    path = await fetch_shard(max_shard)
    return max_shard, path


# ============ 从 git 镜像解析邮件 ============

def _git_log_added_files(
    repo_path: Path,
    since_date: Optional[datetime],
    until_date: Optional[datetime],
) -> list[tuple[str, str]]:
    """用 git log 提取日期范围内每个 commit 变更的文件列表。

    返回 [(commit_sha, filepath), ...]。

    背景：lore.kernel.org 的 LKML 归档使用 public-inbox v2 格式，
    所有邮件存储在仓库根目录的单个文件 `m` 中。每个 commit 修改 `m`
    的内容为当次入库的邮件（commit 的 author/committer date = 邮件日期）。
    因此我们收集 A（新增，浅克隆边界 commit）和 M（修改，常规 commit）
    两种状态，统一用 `git show <sha>:<file>` 读取邮件内容。

    一个 commit 理论上可能修改多个文件，全部收集（实际 v2 只有 `m`）。
    """
    args: list[str] = [
        "git", "--git-dir", str(repo_path),
        "log", "--reverse",
        "--format=@@@COMMIT %H",
        "--name-status",  # 不加 --diff-filter，同时收集 A 和 M
    ]
    if since_date:
        args.append(f"--since={since_date.strftime('%Y-%m-%d %H:%M:%S')}")
    if until_date:
        args.append(f"--until={until_date.strftime('%Y-%m-%d %H:%M:%S')}")

    result = subprocess.run(args, capture_output=True, check=False)
    if result.returncode != 0:
        return []
    output = result.stdout.decode("utf-8", errors="replace")

    entries: list[tuple[str, str]] = []
    current_sha: Optional[str] = None
    for line in output.splitlines():
        if line.startswith("@@@COMMIT "):
            current_sha = line[len("@@@COMMIT "):].strip()
        elif current_sha and (line.startswith("A\t") or line.startswith("M\t")):
            filepath = line[2:].strip()
            if filepath:
                entries.append((current_sha, filepath))
    return entries


def _batch_read_blobs(
    repo_path: Path,
    entries: list[tuple[str, str]],
) -> list[bytes]:
    """批量读取 git blob 内容。entries: [(sha, filepath), ...]。

    使用 git cat-file --batch 一次性读取所有 blob，避免逐个 git show 的进程开销。
    返回与 entries 同序的 bytes 列表（读取失败的项为 b""）。
    """
    if not entries:
        return []
    input_data = "".join(f"{sha}:{fp}\n" for sha, fp in entries).encode("utf-8")

    proc = subprocess.run(
        ["git", "--git-dir", str(repo_path), "cat-file", "--batch"],
        input=input_data, capture_output=True, check=False,
    )
    if proc.returncode != 0:
        # 退化为逐个读取
        return [_read_blob_one(repo_path, sha, fp) for sha, fp in entries]

    stdout = proc.stdout
    results: list[bytes] = []
    pos = 0
    n = len(stdout)
    while pos < n:
        nl = stdout.find(b"\n", pos)
        if nl == -1:
            break
        header = stdout[pos:nl]
        parts = header.split(b" ", 2)
        # 期望格式: "<oid> blob <size>"，失败时为 "<ref> missing"
        if len(parts) >= 3 and parts[1] == b"blob":
            try:
                size = int(parts[2])
            except ValueError:
                pos = nl + 1
                continue
            content_start = nl + 1
            content_end = content_start + size
            results.append(stdout[content_start:content_end])
            pos = content_end + 1  # 跳过内容后的换行
        else:
            # missing 或其他错误，占位
            results.append(b"")
            pos = nl + 1
    # 对齐长度
    while len(results) < len(entries):
        results.append(b"")
    return results[:len(entries)]


def _read_blob_one(repo_path: Path, sha: str, filepath: str) -> bytes:
    """单个 blob 读取（批量失败时的降级路径）。"""
    result = subprocess.run(
        ["git", "--git-dir", str(repo_path), "show", f"{sha}:{filepath}"],
        capture_output=True, check=False,
    )
    return result.stdout if result.returncode == 0 else b""


def parse_git_commits(
    repo_path: Path,
    since_date: Optional[datetime] = None,
    until_date: Optional[datetime] = None,
) -> Iterator[Message]:
    """从 git 镜像按日期范围提取邮件。

    lore.kernel.org 的 git 分片镜像中，每个 commit 添加一个 blob 文件，
    blob 内容为原始 RFC822 邮件（headers + body）。

    - since_date / until_date：按 commit 时间过滤（public-inbox 将 committer
      date 设为邮件 Date）。为防止边界误差，对解析后的邮件 Date header 再做
      一次 Python 侧过滤。
    - 返回 email.message.Message 迭代器
    """
    entries = _git_log_added_files(repo_path, since_date, until_date)
    if not entries:
        return

    blobs = _batch_read_blobs(repo_path, entries)
    for raw in blobs:
        if not raw:
            continue
        try:
            msg = email_lib.message_from_bytes(raw)
        except Exception:  # noqa: BLE001
            continue
        # Python 侧按邮件 Date header 再过滤一次（防止 git 时间漂移）
        if since_date or until_date:
            date_raw = _get_header(msg, "Date")
            if date_raw:
                try:
                    msg_date = parsedate_to_datetime(date_raw)
                    if msg_date.tzinfo is not None:
                        msg_date_utc = msg_date.astimezone(timezone.utc)
                    else:
                        msg_date_utc = msg_date.replace(tzinfo=timezone.utc)
                    if since_date and msg_date_utc < since_date:
                        continue
                    if until_date and msg_date_utc >= until_date:
                        continue
                except (TypeError, ValueError):
                    pass  # 无法解析日期，保留邮件
        yield msg


# ============ 入库 ============

async def _store_emails(messages: list[Message], source: str) -> int:
    """批量入库邮件（按 message_id 去重）。返回新增数量。

    source：记录到 raw_mbox_path 字段，这里改为 git 镜像分片标识
    （例如 "lkml-19.git"），便于追溯邮件来源。
    """
    inserted = 0
    async with async_session_factory() as db:
        for msg in messages:
            message_id = _get_header(msg, "Message-ID").strip("<>")
            if not message_id:
                continue
            existing = await db.execute(select(Email).where(Email.message_id == message_id))
            if existing.scalar_one_or_none():
                continue
            subject = _get_header(msg, "Subject") or "(no subject)"
            author_raw = _get_header(msg, "From")
            addrs = getaddresses([author_raw])
            author = addrs[0][0] or addrs[0][1] or author_raw or "unknown"
            date_raw = _get_header(msg, "Date")
            try:
                date = parsedate_to_datetime(date_raw) if date_raw else datetime.utcnow()
                if date.tzinfo is not None:
                    date = date.astimezone(timezone.utc).replace(tzinfo=None)
            except (TypeError, ValueError):
                date = datetime.utcnow()
            body = _extract_body(msg)
            in_reply_to = _get_header(msg, "In-Reply-To").strip("<>") or None
            refs = _parse_refs(_get_header(msg, "References"))
            is_patch = bool(re.search(r"\[patch[^\]]*\b\d+/\d+\b", subject, re.IGNORECASE)) or subject.lower().startswith("[patch")
            subsystem = detect_subsystem(subject, body)
            patch_id = compute_patch_id(body) if is_patch else None
            email_obj = Email(
                message_id=message_id,
                in_reply_to=in_reply_to,
                subject=subject[:1024],
                author=author[:255],
                date=date,
                body=body,
                patch_id=patch_id,
                refs=refs,
                is_patch=is_patch,
                subsystem=subsystem,
                raw_mbox_path=source,
                reply_count=0,
            )
            db.add(email_obj)
            inserted += 1
        await db.commit()
    return inserted


# ============ 同步入口 ============

def _month_range_utc(year: int, month: int) -> tuple[datetime, datetime]:
    """返回某月的 [起始, 下月起始) UTC 时间范围。"""
    start = datetime(year, month, 1, tzinfo=timezone.utc)
    if month == 12:
        end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        end = datetime(year, month + 1, 1, tzinfo=timezone.utc)
    return start, end


def _list_local_shards() -> list[Path]:
    """列出本地所有 git 分片镜像（按编号升序）。"""
    mirror_dir = settings.lkml_mirror_dir
    if not mirror_dir.exists():
        return []
    return sorted(
        mirror_dir.glob("lkml-*.git"),
        key=lambda p: int(p.stem.split("-")[1]),
    )


async def sync_year_month(year: int, month: int, *, force_refresh: bool = False) -> dict:
    """从 git 分片镜像同步指定月份的邮件到数据库。

    返回 {path, shards, inserted, total, force_refreshed}。

    - force_refresh=True：先 git fetch 最新分片再解析（用于刷新脏数据）
    - force_refresh=False：直接用本地已有镜像解析（不联网）
    - 当月：默认强制 fetch 最新分片（归档会持续追加新邮件）

    注意：历史月份的邮件可能在较旧分片中。若本地只克隆了最新分片，
    历史月份同步会返回 total=0。建议先运行
    scripts/download-lkml-mbox.sh --latest N 下载足够多的分片。
    """
    start, end = _month_range_utc(year, month)
    now = datetime.utcnow()
    is_current_month = (year == now.year and month == now.month)

    fetched_shard: Optional[int] = None
    # 当月：必须 fetch 最新分片（新邮件持续追加）
    # 历史月份且 force_refresh：也 fetch 最新分片（用于更新本地镜像）
    if is_current_month or force_refresh:
        try:
            fetched_shard, _ = await fetch_latest_shard()
        except Exception as exc:  # noqa: BLE001
            # 网络失败时若本地已有镜像则继续，否则报错
            if not _list_local_shards():
                raise RuntimeError(
                    f"fetch 最新分片失败且本地无镜像：{exc}。"
                    f"请先运行 scripts/download-lkml-mbox.sh 下载分片。"
                )

    shard_paths = _list_local_shards()
    if not shard_paths:
        raise RuntimeError(
            f"未找到任何 git 分片镜像（{settings.lkml_mirror_dir}）。"
            f"请先运行 scripts/download-lkml-mbox.sh 下载分片。"
        )

    # 扫描所有本地分片，按日期范围提取邮件
    # git log 的 --since/--until 会自动剔除无关邮件，多分片扫描开销可控
    all_messages: list[Message] = []
    used_shards: list[str] = []
    for sp in shard_paths:
        msgs = await asyncio.to_thread(list, parse_git_commits(sp, start, end))
        if msgs:
            all_messages.extend(msgs)
            used_shards.append(sp.name)

    source = used_shards[0] if used_shards else shard_paths[-1].name
    inserted = await _store_emails(all_messages, source)
    return {
        "path": str(settings.lkml_mirror_dir),
        "shards": used_shards,
        "fetched_shard": fetched_shard,
        "inserted": inserted,
        "total": len(all_messages),
        "force_refreshed": is_current_month or force_refresh,
    }


async def sync_current_month(*, force_refresh: bool = True) -> dict:
    """同步当前月份（默认强制刷新，用于每 6 小时定时任务）。

    当月归档会持续追加新邮件，因此定时任务应强制刷新（git fetch 最新分片）。
    _store_emails 内部按 message_id 去重，重复邮件不会重复入库。
    """
    now = datetime.utcnow()
    return await sync_year_month(now.year, now.month, force_refresh=force_refresh)


async def update_reply_counts() -> int:
    """统计每封邮件的回复数（in_reply_to 指向它）。"""
    async with async_session_factory() as db:
        all_emails = (await db.execute(select(Email))).scalars().all()
        msg_ids = {e.message_id for e in all_emails}
        count_map: dict[str, int] = {e.message_id: 0 for e in all_emails}
        for e in all_emails:
            if e.in_reply_to and e.in_reply_to in count_map:
                count_map[e.in_reply_to] += 1
        for e in all_emails:
            e.reply_count = count_map.get(e.message_id, 0)
        await db.commit()
        return len(all_emails)
