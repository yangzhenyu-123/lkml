"""Celery 实例 + beat schedule。

beat_schedule:
- daily-lkml-sync: 每日 03:00 同步 LKML mbox
- daily-digest:    每日 06:00 生成每日精选文章
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
    "daily-lkml-sync": {
        "task": "app.workers.tasks.sync_lkml_task",
        "schedule": crontab(hour=3, minute=0),
    },
    "daily-digest": {
        "task": "app.workers.tasks.daily_digest_task",
        "schedule": crontab(hour=6, minute=0),
    },
    "weekly-kernel-fetch": {
        "task": "app.workers.tasks.fetch_kernel_task",
        "schedule": crontab(hour=4, minute=0, day_of_week=0),
    },
}
