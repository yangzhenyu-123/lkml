"""Celery 实例 + beat schedule。

beat_schedule:
- lkml-sync-current: 每 6 小时同步当月 LKML mbox（00:00/06:00/12:00/18:00 UTC）
                     当月归档持续追加新邮件，需高频刷新；按 message_id 去重，重复不入库
- daily-digest:      每日 06:30 生成每日精选文章
- weekly-kernel-fetch: 每周日 04:00 拉取 kernel 镜像
"""
from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "lkml_patent",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_default_queue="lkml",
    result_expires=86400,
)

celery_app.conf.beat_schedule = {
    # 每 6 小时同步当月 mbox（00:00/06:00/12:00/18:00 UTC）
    # 当月归档会持续追加新邮件，需高频刷新；按 message_id 去重，重复邮件不会重复入库
    "lkml-sync-current": {
        "task": "app.workers.tasks.sync_lkml_task",
        "schedule": crontab(minute=0, hour="*/6"),
    },
    # 每日 06:30 生成每日精选文章（在 06:00 同步完成后）
    "daily-digest": {
        "task": "app.workers.tasks.daily_digest_task",
        "schedule": crontab(hour=6, minute=30),
    },
    # 每周日 04:00 拉取 kernel 镜像
    "weekly-kernel-fetch": {
        "task": "app.workers.tasks.fetch_kernel_task",
        "schedule": crontab(hour=4, minute=0, day_of_week=0),
    },
}
