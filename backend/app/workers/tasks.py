"""Celery 任务定义。

注意：Celery worker 内同步函数中调用 async 服务时，使用 asyncio.run 包装。
worker 与 API 共享同一份代码与配置。

数据库会话工厂使用 NullPool（见 app/db/session.py），确保每次 asyncio.run
创建新 loop 时不会复用绑定到旧 loop 的 asyncpg 连接。
"""
from __future__ import annotations

import asyncio
from datetime import date as date_type, datetime
from typing import Any, Optional

from app.workers.celery_app import celery_app


def _run(coro):
    """在同步 Celery 任务中执行 async 函数。

    每次调用都创建新的 event loop（asyncio.run），配合 db.session 的 NullPool
    避免跨 loop 复用 asyncpg 连接。
    """
    return asyncio.run(coro)


# ============ LKML 同步 ============
@celery_app.task(name="app.workers.tasks.sync_lkml_task", bind=True)
def sync_lkml_task(
    self,
    year_month: Optional[str] = None,
    *,
    force_refresh: Optional[bool] = None,
) -> dict[str, Any]:
    """同步 LKML mbox。

    - year_month 格式 "YYYY-MM"。不传则取当前月（UTC）。
    - force_refresh：
        None（默认）= 自动判断（当月强制刷新，历史月份复用本地文件）
        True = 强制重新下载覆盖
        False = 永不覆盖，已存在即复用
    """
    from app.services import lkml_sync

    if not year_month:
        # 每日定时任务：当月强制刷新
        now = datetime.utcnow()
        year_month = now.strftime("%Y-%m")
        if force_refresh is None:
            force_refresh = True
        result = _run(lkml_sync.sync_current_month(force_refresh=force_refresh))
    else:
        year, month = year_month.split("-")
        if force_refresh is None:
            # 指定月份：历史月份不刷新，当月根据 mtime 间隔判断
            force_refresh = False
        result = _run(
            lkml_sync.sync_year_month(int(year), int(month), force_refresh=force_refresh)
        )
    # 同步完更新回复数
    _run(lkml_sync.update_reply_counts())
    return {"year_month": year_month, **result}


# ============ Kernel 镜像 fetch ============
@celery_app.task(name="app.workers.tasks.fetch_kernel_task", bind=True)
def fetch_kernel_task(self) -> dict[str, Any]:
    """在 worker 容器内 git fetch kernel 镜像。"""
    from app.services import kernel_mirror

    return _run(kernel_mirror.fetch_latest())


# ============ 流水线 ============
@celery_app.task(name="app.workers.tasks.run_pipeline_task", bind=True)
def run_pipeline_task(self, job_id: int) -> dict[str, Any]:
    """运行完整 4 阶段流水线。"""
    from app.services import pipeline

    _run(pipeline.run_job(job_id))
    return {"job_id": job_id, "status": "completed"}


@celery_app.task(name="app.workers.tasks.run_stage_item_task", bind=True)
def run_stage_item_task(self, item_id: int) -> dict[str, Any]:
    """重试单个 stage item（Stage 3 / 4）。"""
    from app.services import pipeline

    _run(pipeline.run_single_item(item_id))
    return {"item_id": item_id, "status": "completed"}


@celery_app.task(name="app.workers.tasks.retry_stage_item_task", bind=True)
def retry_stage_item_task(self, item_id: int) -> dict[str, Any]:
    """重试入口（别名，调用 run_stage_item_task）。"""
    return run_stage_item_task.apply(args=(item_id,)).get()


# ============ 每日精选 ============
@celery_app.task(name="app.workers.tasks.daily_digest_task", bind=True)
def daily_digest_task(self, date_str: Optional[str] = None) -> dict[str, Any]:
    """生成每日文章并通知订阅者。"""
    from app.services import daily_digest, notifier

    if date_str:
        target_date = date_type.fromisoformat(date_str)
    else:
        target_date = datetime.utcnow().date()

    article = _run(daily_digest.generate_article(target_date))
    if not article:
        return {"date": target_date.isoformat(), "ok": False, "reason": "no emails"}

    # 通知订阅者
    sent = _run(
        notifier.notify_subscribers(
            "daily",
            {
                "subject": article.title,
                "body": article.summary or "",
                "subsystem": None,
            },
        )
    )
    return {
        "date": target_date.isoformat(),
        "ok": True,
        "article_id": article.id,
        "notified": sent,
    }
