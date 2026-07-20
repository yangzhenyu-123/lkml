"""订阅 schema。"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class SubscriptionCreate(BaseModel):
    type: str = Field(..., description="daily / stage_completed / patent_published")
    subsystem_filter: Optional[str] = None
    email_notify: bool = True


class SubscriptionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    type: str
    subsystem_filter: Optional[str] = None
    email_notify: bool
    unsubscribe_token: Optional[str] = None
    created_at: datetime


class SubscriptionList(BaseModel):
    total: int
    items: list[SubscriptionRead]


class UnsubscribeResponse(BaseModel):
    ok: bool
    message: str
