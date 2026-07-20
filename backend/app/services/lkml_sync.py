"""LKML 邮件同步服务：下载 lore.kernel.org mbox、解析、入库、计算 patch-id、识别子系统。"""
from __future__ import annotations

import asyncio
import hashlib
import mailbox
import re
from datetime import datetime, timezone
from email.message import Message
from email.utils import getaddresses, parsedate_to_datetime
from pathlib import Path
from typing import AsyncIterator, Iterator, Optional

import aiohttp
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
    """用 mailbox.mbox 迭代解析邮件。"""
    mbox = mailbox.mbox(str(mbox_path))
    try:
        for msg in mbox:
            yield msg
    finally:
        mbox.close()


async def download_mbox(year: int, month: int, *, session: Optional[aiohttp.ClientSession] = None) -> Path:
    """下载 https://lore.kernel.org/linux-kernel/{YYYY}-{MM}.mbox 到 LKML_MBOX_PATH。

    返回本地文件路径。如已存在则直接复用。
    """
    fname = f"{year:04d}-{month:02d}.mbox"
    target = settings.lkml_mbox_dir / fname
    if target.exists() and target.stat().st_size > 0:
        return target

    url = f"{settings.LKML_BASE_URL.rstrip('/')}/{fname}"
    own_session = session is None
    if own_session:
        session = aiohttp.ClientSession()
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=600)) as resp:  # type: ignore[union-attr]
            if resp.status != 200:
                raise RuntimeError(f"Failed to download {url}: HTTP {resp.status}")
            data = await resp.read()
        target.write_bytes(data)
        return target
    finally:
        if own_session and session is not None:
            await session.close()


async def _store_emails(messages: list[Message], raw_mbox_path: Path) -> int:
    """批量入库邮件（按 message_id 去重）。返回新增数量。"""
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
                raw_mbox_path=str(raw_mbox_path),
                reply_count=0,
            )
            db.add(email_obj)
            inserted += 1
        await db.commit()
    return inserted


async def sync_year_month(year: int, month: int) -> dict:
    """下载 + 解析 + 入库。返回 {path, inserted}。"""
    path = await download_mbox(year, month)
    # parse_mbox 是同步迭代器，放到默认 executor 中执行以避免阻塞事件循环
    messages = await asyncio.to_thread(list, list(parse_mbox(path)))
    inserted = await _store_emails(messages, path)
    return {"path": str(path), "inserted": inserted, "total": len(messages)}


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
