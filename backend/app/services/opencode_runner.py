"""OpenCode Runner：调用 opencode CLI 子进程，加载技能，捕获输出。

约定 CLI（具体参数需对照 opencode 官方文档，已加 TODO 标注）：
    opencode run --skill {skill_path} --prompt {prompt} --output {output_path}

环境变量（从 OpenCodeConfig.env_json 注入）：
    OPENCODE_API_BASE, OPENCODE_API_KEY, OPENCODE_MODEL 等
"""
from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.core.config import settings
from app.schemas.opencode import OpenCodeTestResult

# TODO: 对照 opencode 官方 CLI 文档确认实际命令与参数：
#   - 子命令是 `run` 还是 `exec`？
#   - 是否支持 --skill / --prompt / --output？
#   - 是否支持 --model / --max-tokens / --timeout？
# 当前实现按约定执行；运行时若 opencode 命令不存在，会返回 ok=False。


@dataclass
class RunResult:
    ok: bool
    output_path: Optional[str]
    log_path: Optional[str]
    token_usage: int
    error: Optional[str] = None


def _skills_root() -> Path:
    p = settings.opencode_config_dir / "skills"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _outputs_root() -> Path:
    p = settings.outputs_dir
    p.mkdir(parents=True, exist_ok=True)
    return p


def _build_env(api_base: str, api_key: str, model: str, extra: Optional[dict] = None) -> dict:
    env = os.environ.copy()
    env.update(
        {
            "OPENCODE_API_BASE": api_base,
            "OPENCODE_API_KEY": api_key,
            "OPENCODE_MODEL": model,
        }
    )
    if extra:
        # 注意：env_json 可能包含敏感信息，运行时注入子进程环境
        for k, v in extra.items():
            if isinstance(v, str | int | float | bool):
                env[str(k)] = str(v)
    return env


async def ensure_skills(skills: list) -> None:
    """检查并 git clone/pull 已启用的 skill 仓库到 OPENCODE_CONFIG_PATH/skills/。

    参数 skills: list[SkillConfig]（来自 ORM 对象）
    """
    root = _skills_root()
    for skill in skills:
        if not skill.enabled or not skill.git_url:
            continue
        name = skill.name
        target = Path(skill.local_path) if skill.local_path else root / name
        target.mkdir(parents=True, exist_ok=True)
        is_git_repo = (target / ".git").exists()
        try:
            if is_git_repo:
                await asyncio.to_thread(
                    _run_subprocess_sync,
                    ["git", "-C", str(target), "pull", "--ff-only"],
                    None,
                )
            else:
                branch_args = ["-b", skill.branch] if skill.branch else []
                await asyncio.to_thread(
                    _run_subprocess_sync,
                    ["git", "clone", "--depth", "1", *branch_args, skill.git_url, str(target)],
                    None,
                )
        except RuntimeError:
            # clone/pull 失败不阻断流程，记录到 stderr
            continue


def _run_subprocess_sync(cmd: list[str], env: Optional[dict], cwd: Optional[str] = None) -> str:
    import subprocess

    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            timeout=1800,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(f"command not found: {cmd[0]}") from exc
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "subprocess failed")
    return proc.stdout


async def _run_opencode(
    *,
    skill_path: str,
    prompt: str,
    output_path: Path,
    log_path: Path,
    api_base: str,
    api_key: str,
    model: str,
    timeout: int,
    extra_env: Optional[dict] = None,
) -> RunResult:
    """实际调用 opencode CLI。

    TODO: 对照 opencode 官方 CLI 文档调整命令与参数。
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    env = _build_env(api_base, api_key, model, extra_env)
    cmd = [
        "opencode",
        "run",
        "--skill", skill_path,
        "--prompt", prompt,
        "--output", str(output_path),
    ]
    start = time.time()
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError:
        return RunResult(False, None, None, 0, error="opencode CLI not installed")
    try:
        stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        log_path.write_bytes(b"TIMEOUT\n")
        return RunResult(False, None, str(log_path), 0, error="timeout")

    stdout = stdout_b.decode("utf-8", errors="replace") if stdout_b else ""
    stderr = stderr_b.decode("utf-8", errors="replace") if stderr_b else ""
    log_content = f"$ {' '.join(cmd)}\n--- STDOUT ---\n{stdout}\n--- STDERR ---\n{stderr}\n"
    log_path.write_text(log_content, encoding="utf-8")

    ok = proc.returncode == 0 and output_path.exists()
    token_usage = _extract_token_usage(stdout)
    if ok and not output_path.stat().st_size:
        # 若输出为空，将 stdout 写入 output
        output_path.write_text(stdout, encoding="utf-8")
    return RunResult(
        ok=ok,
        output_path=str(output_path) if ok else None,
        log_path=str(log_path),
        token_usage=token_usage,
        error=None if ok else (stderr.strip() or stdout.strip() or "opencode failed")[:1000],
    )


def _extract_token_usage(stdout: str) -> int:
    """尝试从 opencode 输出中提取 token 使用量。"""
    import re

    m = re.search(r"tokens?\s*[:=]\s*(\d+)", stdout, re.IGNORECASE)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            return 0
    return 0


async def run_optimization(
    *,
    job_id: int,
    item_id: int,
    version: int,
    proposal_context: str,
    prompt_template: str,
    skill_path: Optional[str] = None,
    api_base: str = "",
    api_key: str = "",
    model: str = "",
    timeout: int = 600,
    extra_env: Optional[dict] = None,
) -> RunResult:
    """Stage 3：调用 opencode 生成优化方案。"""
    skill_path = skill_path or str(_skills_root() / "optimization-skill")
    output_path = _outputs_root() / str(job_id) / "stage3" / f"{item_id}_v{version}.md"
    log_path = _outputs_root() / str(job_id) / "stage3" / f"{item_id}_v{version}.log"
    prompt = prompt_template.format(context=proposal_context)
    return await _run_opencode(
        skill_path=skill_path,
        prompt=prompt,
        output_path=output_path,
        log_path=log_path,
        api_base=api_base,
        api_key=api_key,
        model=model,
        timeout=timeout,
        extra_env=extra_env,
    )


async def run_patent_disclosure(
    *,
    job_id: int,
    item_id: int,
    version: int,
    optimization_doc: str,
    prompt_template: str,
    skill_path: Optional[str] = None,
    api_base: str = "",
    api_key: str = "",
    model: str = "",
    timeout: int = 600,
    extra_env: Optional[dict] = None,
) -> RunResult:
    """Stage 4：调用 opencode 生成专利交底书（.md + .docx）。"""
    skill_path = skill_path or str(_skills_root() / "patent-disclosure-skill")
    output_path = _outputs_root() / str(job_id) / "stage4" / f"{item_id}_v{version}.md"
    log_path = _outputs_root() / str(job_id) / "stage4" / f"{item_id}_v{version}.log"
    prompt = prompt_template.format(context=optimization_doc)
    result = await _run_opencode(
        skill_path=skill_path,
        prompt=prompt,
        output_path=output_path,
        log_path=log_path,
        api_base=api_base,
        api_key=api_key,
        model=model,
        timeout=timeout,
        extra_env=extra_env,
    )
    # TODO: 若 opencode 不直接产出 .docx，则后续可调用 pandoc 将 md 转 docx
    return result


async def test_connection(
    *,
    prompt: str,
    api_base: str,
    api_key: str,
    model: str,
    timeout: int = 60,
    extra_env: Optional[dict] = None,
) -> OpenCodeTestResult:
    """运行一次最简单的 opencode 测试，用于 /opencode/test 端点。"""
    output_path = _outputs_root() / "_test" / f"test_{int(time.time())}.md"
    log_path = _outputs_root() / "_test" / f"test_{int(time.time())}.log"
    skill_path = str(_skills_root() / "test-skill")
    # 若 test-skill 不存在，临时创建占位目录
    Path(skill_path).mkdir(parents=True, exist_ok=True)
    start = time.time()
    result = await _run_opencode(
        skill_path=skill_path,
        prompt=prompt,
        output_path=output_path,
        log_path=log_path,
        api_base=api_base,
        api_key=api_key,
        model=model,
        timeout=timeout,
        extra_env=extra_env,
    )
    duration_ms = int((time.time() - start) * 1000)
    output_text = ""
    if result.ok and output_path.exists():
        output_text = output_path.read_text(encoding="utf-8", errors="replace")
    return OpenCodeTestResult(
        ok=result.ok,
        output=output_text,
        error=result.error,
        duration_ms=duration_ms,
        token_usage=result.token_usage,
    )
