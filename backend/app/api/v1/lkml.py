"""LKML 邮件查询与同步路由。"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_analyst
from app.models.email import Email
from app.models.user import User
from app.schemas.lkml import EmailList, EmailRead, SyncRequest, SyncResponse
from app.workers.tasks import sync_lkml_task

router = APIRouter()


def _parse_date(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid date: {s}")


@router.get("/emails", response_model=EmailList)
async def list_emails(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    subsystem: Optional[str] = None,
    is_patch: Optional[bool] = None,
    q: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
) -> EmailList:
    """分页查询 LKML 邮件。"""
    stmt = select(Email)
    count_stmt = select(func.count()).select_from(Email)

    sd = _parse_date(start_date)
    ed = _parse_date(end_date)
    if sd:
        stmt = stmt.where(Email.date >= sd)
        count_stmt = count_stmt.where(Email.date >= sd)
    if ed:
        stmt = stmt.where(Email.date <= ed)
        count_stmt = count_stmt.where(Email.date <= ed)
    if subsystem:
        stmt = stmt.where(Email.subsystem == subsystem)
        count_stmt = count_stmt.where(Email.subsystem == subsystem)
    if is_patch is not None:
        stmt = stmt.where(Email.is_patch == is_patch)
        count_stmt = count_stmt.where(Email.is_patch == is_patch)
    if q:
        like = f"%{q}%"
        cond = or_(Email.subject.ilike(like), Email.body.ilike(like), Email.author.ilike(like))
        stmt = stmt.where(cond)
        count_stmt = count_stmt.where(cond)

    total = (await db.execute(count_stmt)).scalar_one()
    stmt = stmt.order_by(Email.date.desc()).offset(skip).limit(limit)
    rows = (await db.execute(stmt)).scalars().all()
    return EmailList(total=total, skip=skip, limit=limit, items=[EmailRead.model_validate(r) for r in rows])


@router.get("/search", response_model=EmailList)
async def search_emails(
    q: str = Query(..., min_length=1),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
) -> EmailList:
    """关键词搜索邮件（subject / body / author）。"""
    like = f"%{q}%"
    cond = or_(Email.subject.ilike(like), Email.body.ilike(like), Email.author.ilike(like))
    total = (await db.execute(select(func.count()).select_from(Email).where(cond))).scalar_one()
    stmt = select(Email).where(cond).order_by(Email.date.desc()).offset(skip).limit(limit)
    rows = (await db.execute(stmt)).scalars().all()
    return EmailList(total=total, skip=skip, limit=limit, items=[EmailRead.model_validate(r) for r in rows])


@router.post("/sync", response_model=SyncResponse)
async def trigger_sync(
    payload: SyncRequest,
    _: User = Depends(require_analyst),
) -> SyncResponse:
    """触发 LKML 同步任务（Celery）。

    - 不传 year_month：同步当前月（默认强制刷新）
    - 传 year_month：同步指定月份（默认不强制刷新，已存在即复用）
    - force_refresh=True：强制重新下载覆盖
    """
    year_month = payload.year_month or datetime.utcnow().strftime("%Y-%m")
    try:
        # 不传 year_month 时默认 force_refresh=True（当月需要刷新）
        if not payload.year_month:
            task = sync_lkml_task.delay(None, force_refresh=True)
        else:
            task = sync_lkml_task.delay(year_month, force_refresh=payload.force_refresh)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to enqueue sync task: {exc}",
        )
    return SyncResponse(task_id=task.id, year_month=year_month, status="queued")
