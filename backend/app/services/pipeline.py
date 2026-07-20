"""4 阶段流水线编排（状态机）。

Stage 1: 扫描 LKML 邮件，按 year/subsystem/keyword 过滤性能优化 PATCH 邮件
Stage 2: 对 Stage 1 item 检测合入情况，**只对未合入的**创建 Stage 2 item
Stage 3: 对每个未合入 item 调用 opencode 生成优化方案（可重试）
Stage 4: 对每个 Stage 3 成功 item 调用 opencode 生成专利交底书（可重试）

状态变更通过 WebSocketManager 推送。
"""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decrypt_secret
from app.core.websocket_manager import ws_manager
from app.db.session import async_session_factory
from app.models.analysis import AnalysisJob, JobItem, StageRecord
from app.models.email import Email
from app.models.opencode_config import OpenCodeConfig, SkillConfig
from app.models.user import User
from app.services import kernel_mirror, lkml_sync, opencode_runner


async def _publish(job_id: int, event_type: str, payload: dict) -> None:
    await ws_manager.publish(job_id, event_type, payload)


async def _get_config(db: AsyncSession) -> tuple[OpenCodeConfig, list[SkillConfig]]:
    cfg = (
        await db.execute(select(OpenCodeConfig).where(OpenCodeConfig.id == 1))
    ).scalar_one_or_none()
    if cfg is None:
        cfg = OpenCodeConfig(
            id=1,
            api_base=None,
            api_key_enc=None,
            model=None,
            timeout=600,
            max_tokens=8192,
            env_json={},
            prompt_templates={},
        )
        db.add(cfg)
        await db.commit()
        await db.refresh(cfg)
    skills = (await db.execute(select(SkillConfig).where(SkillConfig.enabled.is_(True)))).scalars().all()
    return cfg, list(skills)


def _template(cfg: OpenCodeConfig, key: str, default: str) -> str:
    templates = cfg.prompt_templates or {}
    val = templates.get(key) if isinstance(templates, dict) else None
    return val or default


_STAGE3_TEMPLATE = (
    "You are a Linux kernel performance optimization expert. "
    "Based on the following LKML patch proposal, write a concrete optimization "
    "proposal in Markdown with sections: Background, Problem, Proposed Change, "
    "Expected Benefit, Risks, References.\n\nContext:\n{context}"
)
_STAGE4_TEMPLATE = (
    "You are a patent engineer. Based on the following optimization proposal, "
    "draft a patent disclosure document in Markdown with sections: Title, Field, "
    "Background, Summary, Detailed Description, Claims, Abstract.\n\nProposal:\n{context}"
)


# ============ Stage 1 ============
async def _run_stage1(job: AnalysisJob, db: AsyncSession) -> int:
    """扫描 LKML，过滤性能优化 PATCH 邮件，创建 Stage 1 item。"""
    stage = await _mark_stage_running(db, job.id, 1)
    stmt = select(Email).where(
        Email.is_patch.is_(True),
        Email.date >= datetime(job.year_start, 1, 1),
        Email.date < datetime(job.year_end + 1, 1, 1),
    )
    if job.subsystem_filter:
        subs = [s.strip() for s in job.subsystem_filter.split(",") if s.strip()]
        stmt = stmt.where(Email.subsystem.in_(subs))
    rows = (await db.execute(stmt)).scalars().all()

    keyword: Optional[str] = job.keyword_filter
    inserted = 0
    for e in rows:
        if keyword and keyword.lower() not in (e.subject + (e.body or "")).lower():
            continue
        if not lkml_sync.is_performance_related(e.subject, e.body):
            continue
        item = JobItem(
            job_id=job.id,
            stage_no=1,
            title=e.subject[:1024],
            email_message_id=e.message_id,
            patch_id=e.patch_id,
            author=e.author,
            subsystem=e.subsystem,
            status="success",  # Stage 1 仅筛选，直接标记成功
        )
        db.add(item)
        inserted += 1
    stage.total_items = inserted
    stage.success_items = inserted
    stage.status = "completed"
    stage.finished_at = datetime.utcnow()
    await db.commit()
    await _publish(
        job.id,
        "stage_update",
        {"stage_no": 1, "status": "completed", "total_items": inserted},
    )
    return inserted


# ============ Stage 2 ============
async def _run_stage2(job: AnalysisJob, db: AsyncSession) -> int:
    """检测 Stage 1 item 是否合入上游；**仅未合入**的创建 Stage 2 item。"""
    stage = await _mark_stage_running(db, job.id, 2)
    s1_items = (
        await db.execute(
            select(JobItem).where(JobItem.job_id == job.id, JobItem.stage_no == 1)
        )
    ).scalars().all()
    unmerged = 0
    for it in s1_items:
        # 调用 kernel_mirror 检测合入情况
        check = await asyncio.to_thread(
            kernel_mirror.check_merged, it.patch_id or "", it.title or ""
        )
        it.merged_upstream = check["merged"]
        if check["merged"]:
            continue
        unmerged += 1
        s2_item = JobItem(
            job_id=job.id,
            stage_no=2,
            parent_item_id=it.id,
            title=it.title,
            email_message_id=it.email_message_id,
            patch_id=it.patch_id,
            author=it.author,
            subsystem=it.subsystem,
            optimization_type=_guess_optimization_type(it.title or ""),
            merged_upstream=False,
            status="success",  # Stage 2 仅分类，标记成功
        )
        db.add(s2_item)
    stage.total_items = unmerged
    stage.success_items = unmerged
    stage.status = "completed"
    stage.finished_at = datetime.utcnow()
    await db.commit()
    await _publish(
        job.id,
        "stage_update",
        {"stage_no": 2, "status": "completed", "total_items": unmerged},
    )
    return unmerged


def _guess_optimization_type(title: str) -> str:
    t = title.lower()
    if "lock" in t or "spinlock" in t or "mutex" in t:
        return "locking"
    if "batch" in t or "burst" in t:
        return "batching"
    if "cache" in t:
        return "cache"
    if "lazy" in t or "defer" in t:
        return "lazy"
    if "rcu" in t:
        return "rcu"
    if "memory" in t or "alloc" in t:
        return "memory"
    if "sched" in t:
        return "scheduler"
    return "other"


# ============ Stage 3 ============
async def _run_stage3(job: AnalysisJob, db: AsyncSession, cfg: OpenCodeConfig, skills: list) -> int:
    """对每个未合入 item 调用 opencode 生成优化方案。"""
    stage = await _mark_stage_running(db, job.id, 3)
    s2_items = (
        await db.execute(
            select(JobItem).where(
                JobItem.job_id == job.id,
                JobItem.stage_no == 2,
                JobItem.merged_upstream.is_(False),
            )
        )
    ).scalars().all()
    stage.total_items = len(s2_items)
    await db.commit()

    api_key = decrypt_secret(cfg.api_key_enc) if cfg.api_key_enc else ""
    template = _template(cfg, "stage3_optimization", _STAGE3_TEMPLATE)
    success = 0
    failed = 0
    for it in s2_items:
        await _set_item_running(db, it)
        await _publish(job.id, "item_update", _item_payload(it))
        try:
            context = f"Subject: {it.title}\nAuthor: {it.author}\nSubsystem: {it.subsystem}\nPatch-ID: {it.patch_id}\n\nEmail body: {await _fetch_email_body(it.email_message_id)}"
            result = await opencode_runner.run_optimization(
                job_id=job.id,
                item_id=it.id,
                version=it.version,
                proposal_context=context,
                prompt_template=template,
                api_base=cfg.api_base or "",
                api_key=api_key,
                model=cfg.model or "",
                timeout=cfg.timeout,
                extra_env=cfg.env_json,
            )
            it.output_path = result.output_path
            it.log_path = result.log_path
            it.token_usage = result.token_usage
            if result.ok:
                it.status = "success"
                success += 1
            else:
                it.status = "failed"
                it.error_message = result.error
                failed += 1
        except Exception as exc:  # noqa: BLE001
            it.status = "failed"
            it.error_message = str(exc)[:1000]
            failed += 1
        it.finished_at = datetime.utcnow()
        await db.commit()
        await _publish(job.id, "item_update", _item_payload(it))

    stage.success_items = success
    stage.failed_items = failed
    stage.status = "completed" if failed == 0 else "completed"
    stage.finished_at = datetime.utcnow()
    await db.commit()
    await _publish(
        job.id,
        "stage_update",
        {
            "stage_no": 3,
            "status": "completed",
            "total_items": stage.total_items,
            "success_items": success,
            "failed_items": failed,
        },
    )
    return success


# ============ Stage 4 ============
async def _run_stage4(job: AnalysisJob, db: AsyncSession, cfg: OpenCodeConfig, skills: list) -> int:
    """对每个 Stage 3 成功 item 生成专利交底书。"""
    stage = await _mark_stage_running(db, job.id, 4)
    s3_items = (
        await db.execute(
            select(JobItem).where(
                JobItem.job_id == job.id,
                JobItem.stage_no == 3,
                JobItem.status == "success",
            )
        )
    ).scalars().all()
    stage.total_items = len(s3_items)
    await db.commit()

    api_key = decrypt_secret(cfg.api_key_enc) if cfg.api_key_enc else ""
    template = _template(cfg, "stage4_patent", _STAGE4_TEMPLATE)
    success = 0
    failed = 0
    for it in s3_items:
        await _set_item_running(db, it)
        await _publish(job.id, "item_update", _item_payload(it))
        try:
            # 读取 Stage 3 产出文件作为输入
            optimization_doc = ""
            if it.output_path:
                from pathlib import Path

                p = Path(it.output_path)
                if p.exists():
                    optimization_doc = p.read_text(encoding="utf-8", errors="replace")
            result = await opencode_runner.run_patent_disclosure(
                job_id=job.id,
                item_id=it.id,
                version=it.version,
                optimization_doc=optimization_doc or f"Title: {it.title}",
                prompt_template=template,
                api_base=cfg.api_base or "",
                api_key=api_key,
                model=cfg.model or "",
                timeout=cfg.timeout,
                extra_env=cfg.env_json,
            )
            it.output_path = result.output_path
            it.log_path = result.log_path
            it.token_usage = result.token_usage
            if result.ok:
                it.status = "success"
                success += 1
            else:
                it.status = "failed"
                it.error_message = result.error
                failed += 1
        except Exception as exc:  # noqa: BLE001
            it.status = "failed"
            it.error_message = str(exc)[:1000]
            failed += 1
        it.finished_at = datetime.utcnow()
        await db.commit()
        await _publish(job.id, "item_update", _item_payload(it))

    stage.success_items = success
    stage.failed_items = failed
    stage.status = "completed"
    stage.finished_at = datetime.utcnow()
    await db.commit()
    await _publish(
        job.id,
        "stage_update",
        {
            "stage_no": 4,
            "status": "completed",
            "total_items": stage.total_items,
            "success_items": success,
            "failed_items": failed,
        },
    )
    return success


# ============ 公共辅助 ============
async def _mark_stage_running(db: AsyncSession, job_id: int, stage_no: int) -> StageRecord:
    stage = (
        await db.execute(
            select(StageRecord).where(
                StageRecord.job_id == job_id, StageRecord.stage_no == stage_no
            )
        )
    ).scalar_one_or_none()
    if stage is None:
        stage = StageRecord(job_id=job_id, stage_no=stage_no, status="running")
        db.add(stage)
    stage.status = "running"
    stage.started_at = datetime.utcnow()
    await db.commit()
    await _publish(job_id, "stage_update", {"stage_no": stage_no, "status": "running"})
    return stage


async def _set_item_running(db: AsyncSession, item: JobItem) -> None:
    item.status = "running"
    item.started_at = datetime.utcnow()
    await db.commit()


def _item_payload(item: JobItem) -> dict:
    return {
        "item_id": item.id,
        "stage_no": item.stage_no,
        "status": item.status,
        "version": item.version,
        "output_path": item.output_path,
        "error_message": item.error_message,
    }


async def _fetch_email_body(message_id: Optional[str]) -> str:
    if not message_id:
        return ""
    async with async_session_factory() as db:
        e = (
            await db.execute(select(Email).where(Email.message_id == message_id))
        ).scalar_one_or_none()
        return (e.body or "")[:4000] if e else ""


# ============ 入口 ============
async def run_job(job_id: int) -> None:
    """运行整个 4 阶段流水线。"""
    async with async_session_factory() as db:
        job = (
            await db.execute(select(AnalysisJob).where(AnalysisJob.id == job_id))
        ).scalar_one_or_none()
        if not job:
            return
        job.status = "running"
        job.started_at = datetime.utcnow()
        await db.commit()
        await _publish(job_id, "job_update", {"status": "running"})

        try:
            cfg, skills = await _get_config(db)
            await opencode_runner.ensure_skills(skills)

            job.current_stage = 1
            job.status = "stage1"
            await db.commit()
            await _publish(job_id, "job_update", {"status": "stage1", "current_stage": 1})
            await _run_stage1(job, db)

            job.current_stage = 2
            job.status = "stage2"
            await db.commit()
            await _publish(job_id, "job_update", {"status": "stage2", "current_stage": 2})
            await _run_stage2(job, db)

            job.current_stage = 3
            job.status = "stage3"
            await db.commit()
            await _publish(job_id, "job_update", {"status": "stage3", "current_stage": 3})
            await _run_stage3(job, db, cfg, skills)

            job.current_stage = 4
            job.status = "stage4"
            await db.commit()
            await _publish(job_id, "job_update", {"status": "stage4", "current_stage": 4})
            await _run_stage4(job, db, cfg, skills)

            job.status = "completed"
            job.finished_at = datetime.utcnow()
            await db.commit()
            await _publish(job_id, "job_update", {"status": "completed"})
        except Exception as exc:  # noqa: BLE001
            job.status = "failed"
            job.error_message = str(exc)[:2000]
            job.finished_at = datetime.utcnow()
            await db.commit()
            await _publish(
                job_id,
                "job_update",
                {"status": "failed", "error_message": job.error_message},
            )


async def run_single_item(item_id: int) -> None:
    """重试单个 Stage 3 / 4 item。"""
    async with async_session_factory() as db:
        item = (
            await db.execute(select(JobItem).where(JobItem.id == item_id))
        ).scalar_one_or_none()
        if not item:
            return
        job_id = item.job_id
        await _set_item_running(db, item)
        await _publish(job_id, "item_update", _item_payload(item))

        cfg, skills = await _get_config(db)
        api_key = decrypt_secret(cfg.api_key_enc) if cfg.api_key_enc else ""
        try:
            if item.stage_no == 3:
                template = _template(cfg, "stage3_optimization", _STAGE3_TEMPLATE)
                context = f"Subject: {item.title}\nAuthor: {item.author}\nSubsystem: {item.subsystem}\nPatch-ID: {item.patch_id}"
                result = await opencode_runner.run_optimization(
                    job_id=job_id,
                    item_id=item.id,
                    version=item.version,
                    proposal_context=context,
                    prompt_template=template,
                    api_base=cfg.api_base or "",
                    api_key=api_key,
                    model=cfg.model or "",
                    timeout=cfg.timeout,
                    extra_env=cfg.env_json,
                )
            elif item.stage_no == 4:
                template = _template(cfg, "stage4_patent", _STAGE4_TEMPLATE)
                optimization_doc = ""
                if item.output_path:
                    from pathlib import Path
                    p = Path(item.output_path)
                    if p.exists():
                        optimization_doc = p.read_text(encoding="utf-8", errors="replace")
                result = await opencode_runner.run_patent_disclosure(
                    job_id=job_id,
                    item_id=item.id,
                    version=item.version,
                    optimization_doc=optimization_doc or f"Title: {item.title}",
                    prompt_template=template,
                    api_base=cfg.api_base or "",
                    api_key=api_key,
                    model=cfg.model or "",
                    timeout=cfg.timeout,
                    extra_env=cfg.env_json,
                )
            else:
                item.status = "failed"
                item.error_message = f"Stage {item.stage_no} cannot be retried"
                await db.commit()
                return

            item.output_path = result.output_path
            item.log_path = result.log_path
            item.token_usage = result.token_usage
            item.status = "success" if result.ok else "failed"
            if not result.ok:
                item.error_message = result.error
        except Exception as exc:  # noqa: BLE001
            item.status = "failed"
            item.error_message = str(exc)[:1000]
        item.finished_at = datetime.utcnow()
        await db.commit()
        await _publish(job_id, "item_update", _item_payload(item))
