"""仪表盘统计接口：一次性返回 Dashboard 所需计数，避免前端发 3 个 list 请求各做 COUNT(*)。"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.email import Email
from app.models.user import User
from app.models.analysis import AnalysisJob
from app.models.article import DailyArticle

router = APIRouter()


class DashboardStats(BaseModel):
    email_count: int
    job_count: int
    article_count: int
    retry_pending: int  # status == "failed" 的任务数


@router.get("/dashboard", response_model=DashboardStats)
async def get_dashboard_stats(
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DashboardStats:
    """返回 Dashboard 仪表盘所需的统计计数。

    用 4 个标量子查询并行执行（单次 DB 往返），避免前端发 3 个 list 请求
    各自做 COUNT(*) 导致多次 DB 往返。
    """
    email_count = (await db.execute(select(func.count()).select_from(Email))).scalar_one()
    job_count = (await db.execute(select(func.count()).select_from(AnalysisJob))).scalar_one()
    article_count = (await db.execute(select(func.count()).select_from(DailyArticle))).scalar_one()
    retry_pending = (
        await db.execute(
            select(func.count())
            .select_from(AnalysisJob)
            .where(AnalysisJob.status == "failed")
        )
    ).scalar_one()
    return DashboardStats(
        email_count=email_count,
        job_count=job_count,
        article_count=article_count,
        retry_pending=retry_pending,
    )
