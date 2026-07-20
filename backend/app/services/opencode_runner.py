"""OpenCode Runner：调用 opencode CLI 子进程，加载技能上下文，捕获输出。

OpenCode CLI 真实用法（详见 https://opencode.ai/docs/cli）：
    opencode run "<prompt>" --model <provider/model> [--agent <name>] [--continue] [--session <id>]

关键约定：
- prompt 是位置参数（不支持 --prompt 标志）
- model 格式必须为 `provider/model`（如 openai/gpt-4o、anthropic/claude-sonnet-4-5）
- 输出通过 stdout 返回，由本模块捕获并写入文件
- 认证通过环境变量注入（OPENAI_API_KEY / ANTHROPIC_API_KEY / GOOGLE_API_KEY 等）
- skills 通过将其 SKILL.md 内容拼接到 prompt 前缀实现（opencode 本身无 --skill 标志）

环境变量（从 OpenCodeConfig.env_json 注入子进程）：
    OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY, OPENCODE_API_BASE, ...
"""
from __future__ import annotations

import asyncio
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.core.config import settings
from app.schemas.opencode import OpenCodeTestResult


@dataclass
class RunResult:
    ok: bool
    output_path: Optional[str]
    log_path: Optional[str]
    token_usage: int
    error: Optional[str] = None


# ============ 路径辅助 ============

def _skills_root() -> Path:
    p = settings.opencode_config_dir / "skills"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _outputs_root() -> Path:
    p = settings.outputs_dir
    p.mkdir(parents=True, exist_ok=True)
    return p


# ============ 模型格式校验 ============

# 已知的 provider 前缀（详见 https://opencode.ai/docs/providers）
_KNOWN_PROVIDERS = {
    "openai", "anthropic", "google", "google-vertex", "azure",
    "aws-bedrock", "groq", "mistral", "deepseek", "kimi",
    "opencode", "ollama", "lmstudio", "together", "fireworks",
}


def _normalize_model(model: str) -> str:
    """规范化模型字符串为 provider/model 格式。

    若用户填写 `gpt-4o` 则补全为 `openai/gpt-4o`；
    若已是 `provider/model` 格式则原样返回。
    """
    if not model:
        return "openai/gpt-4o"
    if "/" in model:
        return model
    # 猜测 provider
    low = model.lower()
    if low.startswith(("gpt-", "o1", "o3", "o4")):
        return f"openai/{model}"
    if low.startswith("claude"):
        return f"anthropic/{model}"
    if low.startswith(("gemini", "gemma")):
        return f"google/{model}"
    if low.startswith("deepseek"):
        return f"deepseek/{model}"
    if low.startswith("grok"):
        return f"opencode/{model}"
    if low.startswith("llama") or low.startswith("qwen"):
        return f"ollama/{model}"
    # 默认 openai
    return f"openai/{model}"


def _provider_env_key(model: str) -> str:
    """根据 model 推断对应的 API key 环境变量名。"""
    provider = model.split("/", 1)[0].lower() if "/" in model else "openai"
    mapping = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "google": "GOOGLE_API_KEY",
        "google-vertex": "GOOGLE_APPLICATION_CREDENTIALS",
        "azure": "AZURE_API_KEY",
        "aws-bedrock": "AWS_BEDROCK_API_KEY",
        "groq": "GROQ_API_KEY",
        "mistral": "MISTRAL_API_KEY",
        "deepseek": "DEEPSEEK_API_KEY",
        "kimi": "MOONSHOT_API_KEY",
        "opencode": "OPENCODE_API_KEY",
    }
    return mapping.get(provider, "OPENAI_API_KEY")


# ============ 环境构造 ============

def _build_env(
    api_base: str,
    api_key: str,
    model: str,
    extra: Optional[dict] = None,
) -> dict:
    """构造子进程环境：注入 API key 与 endpoint。

    OpenCode 通过 provider 专属环境变量识别凭据（如 OPENAI_API_KEY）。
    若 OpenCodeConfig.api_key_enc 不为空，则同时设置 OPENAI_API_KEY 与
    OPENCODE_API_KEY，覆盖大多数 provider 场景。
    """
    env = os.environ.copy()
    # 注入用户自定义 env_json（最高优先级，可覆盖任意 key）
    if extra:
        for k, v in extra.items():
            if isinstance(v, (str, int, float, bool)):
                env[str(k)] = str(v)
    # 注入 api_key 到 provider 对应的环境变量
    if api_key:
        env_key = _provider_env_key(model)
        env[env_key] = api_key
        # 同时设置 OPENCODE_API_KEY 作为兜底（opencode 内部识别）
        env["OPENCODE_API_KEY"] = api_key
    # 注入 api_base（OpenAI 兼容端点）
    if api_base:
        env["OPENAI_API_BASE"] = api_base
        env["OPENCODE_API_BASE"] = api_base
    return env


# ============ Skill 上下文加载 ============

def _load_skill_context(skill_name: str) -> str:
    """加载 skill 的 SKILL.md 内容作为 prompt 前缀。

    OpenCode 没有 --skill 标志，AgentSkills 标准的 skill 通过将其
    SKILL.md 内容拼到 prompt 前缀实现"技能激活"。
    """
    skill_dir = _skills_root() / skill_name
    skill_md = skill_dir / "SKILL.md"
    if skill_md.exists():
        try:
            content = skill_md.read_text(encoding="utf-8", errors="replace")
            return (
                "# 激活技能\n\n"
                "请严格按照以下技能说明执行任务：\n\n"
                "---\n\n"
                f"{content}\n\n"
                "---\n\n"
                "# 任务\n\n"
            )
        except OSError:
            pass
    return ""


# ============ Skills git clone/pull ============

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


# ============ 核心 opencode 调用 ============

async def _run_opencode(
    *,
    prompt: str,
    output_path: Path,
    log_path: Path,
    api_base: str,
    api_key: str,
    model: str,
    timeout: int,
    extra_env: Optional[dict] = None,
    skill_name: Optional[str] = None,
) -> RunResult:
    """实际调用 opencode CLI 子进程。

    命令：opencode run "<prompt>" --model <provider/model> --format text
    输出捕获 stdout 后写入 output_path。
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # 加载技能上下文（拼到 prompt 前缀）
    skill_prefix = ""
    if skill_name:
        skill_prefix = _load_skill_context(skill_name)
    full_prompt = f"{skill_prefix}{prompt}"

    # 规范化 model 为 provider/model 格式
    normalized_model = _normalize_model(model)

    # 构造环境
    env = _build_env(api_base, api_key, normalized_model, extra_env)

    # opencode run "<prompt>" --model <provider/model>
    # 注意：prompt 作为位置参数必须放在 --model 之前
    cmd = [
        "opencode",
        "run",
        full_prompt,
        "--model",
        normalized_model,
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
        log_path.write_bytes(f"$ {' '.join(cmd[:3])} ... --model {normalized_model}\nTIMEOUT after {timeout}s\n".encode())
        return RunResult(False, None, str(log_path), 0, error="timeout")

    elapsed = time.time() - start
    stdout = stdout_b.decode("utf-8", errors="replace") if stdout_b else ""
    stderr = stderr_b.decode("utf-8", errors="replace") if stderr_b else ""

    # 写日志（不记录完整 prompt 避免泄露敏感内容）
    log_content = (
        f"$ opencode run <prompt> --model {normalized_model}\n"
        f"elapsed: {elapsed:.2f}s\n"
        f"returncode: {proc.returncode}\n"
        f"--- STDOUT ({len(stdout)} chars) ---\n{stdout}\n"
        f"--- STDERR ---\n{stderr}\n"
    )
    log_path.write_text(log_content, encoding="utf-8")

    ok = proc.returncode == 0 and bool(stdout.strip())
    token_usage = _extract_token_usage(stdout, stderr)

    if ok:
        # stdout 即为产出内容，写入 output_path
        output_path.write_text(stdout, encoding="utf-8")
        return RunResult(
            ok=True,
            output_path=str(output_path),
            log_path=str(log_path),
            token_usage=token_usage,
        )
    return RunResult(
        ok=False,
        output_path=None,
        log_path=str(log_path),
        token_usage=token_usage,
        error=(stderr.strip() or stdout.strip() or f"opencode exited with {proc.returncode}")[:1000],
    )


def _extract_token_usage(stdout: str, stderr: str = "") -> int:
    """尝试从 opencode 输出中提取 token 使用量。

    opencode run 默认输出纯文本回复，token 信息可能在 stderr 或
    使用 --format json 时出现在 stdout 的 JSON 字段中。
    """
    # 尝试 JSON 格式：{"tokens": 1234} 或 {"usage": {"total_tokens": 1234}}
    combined = f"{stdout}\n{stderr}"
    patterns = [
        r'"total_tokens"\s*:\s*(\d+)',
        r'"tokens"\s*:\s*(\d+)',
        r'"usage".*?"total_tokens"\s*:\s*(\d+)',
        r'tokens?\s*[:=]\s*(\d+)',
    ]
    for pat in patterns:
        m = re.search(pat, combined, re.IGNORECASE)
        if m:
            try:
                return int(m.group(1))
            except ValueError:
                continue
    return 0


# ============ 业务入口 ============

async def run_optimization(
    *,
    job_id: int,
    item_id: int,
    version: int,
    proposal_context: str,
    prompt_template: str,
    api_base: str = "",
    api_key: str = "",
    model: str = "",
    timeout: int = 600,
    extra_env: Optional[dict] = None,
) -> RunResult:
    """Stage 3：调用 opencode 生成优化方案。

    使用 optimization-skill 技能上下文（若已 clone），否则纯 prompt。
    """
    skill_name = "optimization-skill"
    output_path = _outputs_root() / str(job_id) / "stage3" / f"{item_id}_v{version}.md"
    log_path = _outputs_root() / str(job_id) / "stage3" / f"{item_id}_v{version}.log"
    prompt = prompt_template.format(context=proposal_context)
    return await _run_opencode(
        prompt=prompt,
        output_path=output_path,
        log_path=log_path,
        api_base=api_base,
        api_key=api_key,
        model=model,
        timeout=timeout,
        extra_env=extra_env,
        skill_name=skill_name,
    )


async def run_patent_disclosure(
    *,
    job_id: int,
    item_id: int,
    version: int,
    optimization_doc: str,
    prompt_template: str,
    api_base: str = "",
    api_key: str = "",
    model: str = "",
    timeout: int = 600,
    extra_env: Optional[dict] = None,
) -> RunResult:
    """Stage 4：调用 opencode + patent-disclosure-skill 生成专利交底书。

    使用 patent-disclosure-skill 技能上下文（若已 clone）。
    产出 .md；.docx 转换由后续流程处理（可选 pandoc）。
    """
    skill_name = "patent-disclosure-skill"
    output_path = _outputs_root() / str(job_id) / "stage4" / f"{item_id}_v{version}.md"
    log_path = _outputs_root() / str(job_id) / "stage4" / f"{item_id}_v{version}.log"
    prompt = prompt_template.format(context=optimization_doc)
    return await _run_opencode(
        prompt=prompt,
        output_path=output_path,
        log_path=log_path,
        api_base=api_base,
        api_key=api_key,
        model=model,
        timeout=timeout,
        extra_env=extra_env,
        skill_name=skill_name,
    )


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
    start = time.time()
    result = await _run_opencode(
        prompt=prompt,
        output_path=output_path,
        log_path=log_path,
        api_base=api_base,
        api_key=api_key,
        model=model,
        timeout=timeout,
        extra_env=extra_env,
        skill_name=None,  # 测试不加载 skill
    )
    duration_ms = int((time.time() - start) * 1000)
    output_text = ""
    if result.ok and output_path.exists():
        output_text = output_path.read_text(encoding="utf-8", errors="replace")
    elif result.log_path and Path(result.log_path).exists():
        # 失败时返回日志末尾便于排查
        try:
            log_text = Path(result.log_path).read_text(encoding="utf-8", errors="replace")
            output_text = log_text[-2000:]
        except OSError:
            pass
    return OpenCodeTestResult(
        ok=result.ok,
        output=output_text,
        error=result.error,
        duration_ms=duration_ms,
        token_usage=result.token_usage,
    )
