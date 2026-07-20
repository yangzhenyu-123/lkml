"""每日精选技术文章生成。"""
from __future__ import annotations

import asyncio
from datetime import date as date_type, datetime, timedelta
from pathlib import Path
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import decrypt_secret
from app.db.session import async_session_factory
from app.models.article import DailyArticle
from app.models.email import Email
from app.models.opencode_config import OpenCodeConfig, SkillConfig
from app.services import lkml_sync, opencode_runner

_DIGEST_TEMPLATE = (
    "Summarize the following LKML emails into a single technical daily digest "
    "article in Markdown. Group by subsystem. Highlight patches, discussions, and "
    "performance-related changes.\n\nEmails:\n{context}"
)

# 维护者关键词（简化版，实际可从 MAINTAINERS 文件加载）
_MAINTAINER_KEYWORDS = [
    "linus torvalds", "andrew morton", "greg kroah-hartman",
    "david miller", "arnd bergmann", "peter zijlstra",
    "mingo", "akpm", "tejun", "david s. miller",
]


def score_email(email: Email) -> float:
    """计算邮件重要度分数。"""
    score = (email.reply_count or 0) * 2.0
    author_lower = (email.author or "").lower()
    if any(m in author_lower for m in _MAINTAINER_KEYWORDS):
        score += 5.0
    if email.is_patch:
        score += 3.0
    subject_lower = (email.subject or "").lower()
    if lkml_sync.is_performance_related(email.subject, email.body):
        score += 2.0
    if "[rfc" in subject_lower or "[request" in subject_lower:
        score += 1.0
    return score


async def _fetch_emails_of_day(target_date: date_type) -> list[Email]:
    start = datetime.combine(target_date, datetime.min.time())
    end = start + timedelta(days=1)
    async with async_session_factory() as db:
        rows = (
            await db.execute(
                select(Email).where(Email.date >= start, Email.date < end).order_by(Email.date)
            )
        ).scalars().all()
        return list(rows)


def _cluster_by_subsystem(emails: list[Email]) -> dict[str, list[Email]]:
    clusters: dict[str, list[Email]] = {}
    for e in emails:
        sub = e.subsystem or "misc"
        clusters.setdefault(sub, []).append(e)
    return clusters


async def generate_article(target_date: date_type) -> Optional[DailyArticle]:
    """生成某日的技术文章。"""
    emails = await _fetch_emails_of_day(target_date)
    if not emails:
        return None

    scored = sorted(emails, key=score_email, reverse=True)
    top = scored[:200]
    clusters = _cluster_by_subsystem(top)

    # 构造 opencode 输入
    lines: list[str] = []
    for sub, items in clusters.items():
        lines.append(f"## {sub}")
        for e in items[:20]:
            lines.append(f"- [{e.date.isoformat()}] {e.subject} -- {e.author}")
            if e.body:
                lines.append(f"  > {e.body[:300].strip()}")
    context = "\n".join(lines)

    # 写入文件
    content_path = settings.outputs_dir / "daily" / f"{target_date.isoformat()}.md"
    content_path.parent.mkdir(parents=True, exist_ok=True)

    # 尝试调用 opencode 生成；失败则用模板
    async with async_session_factory() as db:
        cfg = (
            await db.execute(select(OpenCodeConfig).where(OpenCodeConfig.id == 1))
        ).scalar_one_or_none()
        api_key = decrypt_secret(cfg.api_key_enc) if cfg and cfg.api_key_enc else ""
        skills = (
            await db.execute(select(SkillConfig).where(SkillConfig.enabled.is_(True)))
        ).scalars().all()
        if cfg:
            await opencode_runner.ensure_skills(list(skills))
            template = (cfg.prompt_templates or {}).get("daily_digest", _DIGEST_TEMPLATE)
            try:
                result = await opencode_runner.run_optimization(
                    job_id=0,
                    item_id=0,
                    version=1,
                    proposal_context=context,
                    prompt_template=template,
                    api_base=cfg.api_base or "",
                    api_key=api_key,
                    model=cfg.model or "",
                    timeout=cfg.timeout,
                    extra_env=cfg.env_json,
                )
                if result.ok and result.output_path:
                    src = Path(result.output_path)
                    if src.exists():
                        content_path.write_text(src.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
                    else:
                        content_path.write_text(context, encoding="utf-8")
                else:
                    content_path.write_text(context, encoding="utf-8")
            except Exception:  # noqa: BLE001
                content_path.write_text(context, encoding="utf-8")
        else:
            content_path.write_text(context, encoding="utf-8")

    # 落库
    title = f"Linux Kernel Daily Digest - {target_date.isoformat()}"
    summary = f"Top {len(top)} emails across {len(clusters)} subsystems."
    subsystems = list(clusters.keys())
    email_ids = [e.message_id for e in top]

    async with async_session_factory() as db:
        existing = (
            await db.execute(select(DailyArticle).where(DailyArticle.date == target_date))
        ).scalar_one_or_none()
        if existing:
            existing.title = title
            existing.summary = summary
            existing.content_path = str(content_path)
            existing.subsystems = subsystems
            existing.email_ids = email_ids
            await db.commit()
            await db.refresh(existing)
            return existing
        article = DailyArticle(
            date=target_date,
            title=title,
            summary=summary,
            content_path=str(content_path),
            subsystems=subsystems,
            email_ids=email_ids,
        )
        db.add(article)
        await db.commit()
        await db.refresh(article)
        return article
