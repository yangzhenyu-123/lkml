"""每日文章路由。"""
from __future__ import annotations

from datetime import date as date_type, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db, require_analyst
from app.models.article import DailyArticle
from app.models.user import User
from app.schemas.article import (
    ArticleList,
    ArticleRead,
    ArticleRegenerateRequest,
    ArticleRegenerateResponse,
)
from app.workers.tasks import daily_digest_task

router = APIRouter()


def _parse_date(s: Optional[str]) -> Optional[date_type]:
    if not s:
        return None
    try:
        return date_type.fromisoformat(s)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid date: {s}")


@router.get("/articles", response_model=ArticleList)
async def list_articles(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> ArticleList:
    df = _parse_date(date_from)
    dt = _parse_date(date_to)
    stmt = select(DailyArticle)
    count_stmt = select(func.count()).select_from(DailyArticle)
    if df:
        stmt = stmt.where(DailyArticle.date >= df)
        count_stmt = count_stmt.where(DailyArticle.date >= df)
    if dt:
        stmt = stmt.where(DailyArticle.date <= dt)
        count_stmt = count_stmt.where(DailyArticle.date <= dt)
    total = (await db.execute(count_stmt)).scalar_one()
    stmt = stmt.order_by(DailyArticle.date.desc()).offset(skip).limit(limit)
    rows = (await db.execute(stmt)).scalars().all()
    return ArticleList(
        total=total,
        skip=skip,
        limit=limit,
        items=[ArticleRead.model_validate(r) for r in rows],
    )


@router.get("/articles/{article_id}", response_model=ArticleRead)
async def get_article(
    article_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> ArticleRead:
    article = (
        await db.execute(select(DailyArticle).where(DailyArticle.id == article_id))
    ).scalar_one_or_none()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    return ArticleRead.model_validate(article)


@router.post("/regenerate", response_model=ArticleRegenerateResponse)
async def regenerate(
    payload: ArticleRegenerateRequest,
    _: User = Depends(require_analyst),
) -> ArticleRegenerateResponse:
    target_date = payload.date or datetime.utcnow().date()
    try:
        task = daily_digest_task.delay(target_date.isoformat())
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to enqueue digest task: {exc}",
        )
    return ArticleRegenerateResponse(task_id=task.id, date=target_date, status="queued")
