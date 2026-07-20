"""LKML 邮件 schema。"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class EmailRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    message_id: str
    in_reply_to: Optional[str] = None
    subject: str
    author: str
    date: datetime
    body: Optional[str] = None
    patch_id: Optional[str] = None
    refs: Optional[List[str]] = None
    is_patch: bool
    subsystem: Optional[str] = None
    raw_mbox_path: Optional[str] = None
    reply_count: int = 0


class EmailList(BaseModel):
    total: int
    skip: int
    limit: int
    items: List[EmailRead]


class SyncRequest(BaseModel):
    year_month: Optional[str] = Field(
        None,
        description="格式 YYYY-MM。不填则同步当前月。",
        pattern=r"^\d{4}-\d{2}$",
    )


class SyncResponse(BaseModel):
    task_id: str
    year_month: str
    status: str = "queued"
