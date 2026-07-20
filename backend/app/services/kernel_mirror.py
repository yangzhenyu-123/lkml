"""Kernel 镜像操作：git log --grep / git patch-id 匹配 / 检测合入。"""
from __future__ import annotations

import asyncio
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.core.config import settings


class KernelMirrorError(RuntimeError):
    pass


def _repo_path() -> Path:
    p = Path(settings.KERNEL_MIRROR_PATH)
    if not (p / ".git").exists() and not p.exists():
        raise KernelMirrorError(f"Kernel mirror not initialized at {p}")
    return p


def _run_git(args: list[str], cwd: Optional[Path] = None) -> str:
    """同步执行 git 命令并返回 stdout。"""
    cmd = ["git"] + args
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd or _repo_path()),
            check=True,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except subprocess.CalledProcessError as exc:
        raise KernelMirrorError(
            f"git {' '.join(args)} failed: {exc.stderr.strip() or exc.stdout.strip()}"
        ) from exc
    return proc.stdout


async def _run_git_async(args: list[str], cwd: Optional[Path] = None) -> str:
    """异步执行 git 命令（在 executor 中）。"""
    return await asyncio.to_thread(_run_git, args, cwd)


def git_log_grep(
    pattern: str,
    since: Optional[str] = None,
    until: Optional[str] = None,
    limit: int = 200,
) -> list[dict]:
    """调用 git log --grep 返回提交列表。

    返回 [{hash, author, date, subject, patch_id}]。
    """
    args = [
        "log",
        f"--grep={pattern}",
        "-i",
        "-E",
        f"-n{limit}",
        "--format=%H%x09%an%x09%ad%x09%s",
        "--date=iso",
    ]
    if since:
        args.append(f"--since={since}")
    if until:
        args.append(f"--until={until}")
    out = _run_git(args)
    results: list[dict] = []
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) < 4:
            continue
        commit_hash, author, date_str, subject = parts[0], parts[1], parts[2], "\t".join(parts[3:])
        results.append(
            {
                "hash": commit_hash,
                "author": author,
                "date": date_str,
                "subject": subject,
                "patch_id": _compute_commit_patch_id(commit_hash),
            }
        )
    return results


def _compute_commit_patch_id(commit_hash: str) -> Optional[str]:
    """对单个 commit 计算 git patch-id。"""
    try:
        diff = _run_git(["show", "--format=", commit_hash])
    except KernelMirrorError:
        return None
    if not diff.strip():
        return None
    try:
        proc = subprocess.run(
            ["git", "patch-id"],
            input=diff,
            cwd=str(_repo_path()),
            capture_output=True,
            text=True,
            timeout=60,
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            return None
        return proc.stdout.strip().split()[0]
    except (subprocess.SubprocessError, FileNotFoundError):
        return None


def find_by_patch_id(patch_id: str) -> Optional[dict]:
    """通过 patch-id 在 kernel 镜像中查找对应 commit。

    实现：取近期 commit 的 patch-id 比对（限制最近 50000 条以控制耗时）。
    生产环境建议预生成 patch-id 索引。
    """
    if not patch_id:
        return None
    try:
        # 一次性输出 hash + patch-id，逐行比对
        proc = subprocess.run(
            ["git", "log", "-p", "--format=#%H", "-n", "50000"],
            cwd=str(_repo_path()),
            capture_output=True,
            text=True,
            timeout=300,
        )
    except subprocess.SubprocessError:
        return None
    if proc.returncode != 0:
        return None
    # 简易解析：每个 commit 以 #<hash> 开始，对其 diff 部分调用 git patch-id
    blocks = re.split(r"^#([0-9a-f]{40})$", proc.stdout, flags=re.MULTILINE)
    # blocks: ['', 'hash1', 'content1', 'hash2', 'content2', ...]
    for i in range(1, len(blocks), 2):
        commit_hash = blocks[i]
        diff_text = blocks[i + 1] if i + 1 < len(blocks) else ""
        if not diff_text.strip():
            continue
        try:
            pid_proc = subprocess.run(
                ["git", "patch-id"],
                input=diff_text,
                cwd=str(_repo_path()),
                capture_output=True,
                text=True,
                timeout=30,
            )
        except subprocess.SubprocessError:
            continue
        if pid_proc.returncode == 0 and pid_proc.stdout.strip():
            current_pid = pid_proc.stdout.strip().split()[0]
            if current_pid == patch_id:
                # 取该 commit 的元信息
                meta = _run_git(["show", "-s", "--format=%an|%ad|%s", "--date=iso", commit_hash])
                author, date_str, subject = (meta.split("|", 2) + ["", "", ""])[:3]
                return {
                    "hash": commit_hash,
                    "author": author,
                    "date": date_str,
                    "subject": subject,
                    "patch_id": current_pid,
                }
    return None


def check_merged(patch_id: str, commit_subject: str) -> dict:
    """检测某个 patch 是否合入上游。返回 {merged, commit_hash, merge_date}。"""
    if not patch_id:
        # 退化为按 subject 关键词搜索
        keywords = [w for w in re.split(r"\W+", commit_subject) if len(w) > 4][:4]
        if not keywords:
            return {"merged": False, "commit_hash": None, "merge_date": None}
        pattern = "|".join(re.escape(k) for k in keywords)
        hits = git_log_grep(pattern, limit=50)
        if hits:
            return {
                "merged": True,
                "commit_hash": hits[0]["hash"],
                "merge_date": hits[0]["date"],
            }
        return {"merged": False, "commit_hash": None, "merge_date": None}
    hit = find_by_patch_id(patch_id)
    if hit:
        return {
            "merged": True,
            "commit_hash": hit["hash"],
            "merge_date": hit.get("date"),
        }
    return {"merged": False, "commit_hash": None, "merge_date": None}


async def fetch_latest() -> dict:
    """在 worker 容器内 git fetch --prune origin，并 fast-forward main 分支。"""
    repo = _repo_path()
    await _run_git_async(["fetch", "--prune", "origin"], cwd=repo)
    # 尝试 fast-forward 主分支（master 或 main）
    for branch in ("master", "main"):
        try:
            await _run_git_async(["checkout", branch], cwd=repo)
            await _run_git_async(["merge", "--ff-only", f"origin/{branch}"], cwd=repo)
            return {"branch": branch, "ok": True}
        except KernelMirrorError:
            continue
    return {"branch": None, "ok": False}
