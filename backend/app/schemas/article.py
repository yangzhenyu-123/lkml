"""每日文章 schema。"""
from __future__ import annotations

from datetime import date as date_type, datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class ArticleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    date: date_type
    title: str
    summary: Optional[str] = None
    content_path: Optional[str] = None
    subsystems: Optional[List[str]] = None
    email_ids: Optional[List[str]] = None
    created_at: datetime


class ArticleList(BaseModel):
    total: int
    skip: int
    limit: int
    items: List[ArticleRead]


class ArticleRegenerateRequest(BaseModel):
    date: Optional[date_type] = None


class ArticleRegenerateResponse(BaseModel):
    task_id: str
    date: date_type
    status: str = "queued"
