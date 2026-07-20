"""LKML 邮件模型。"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import Boolean, DateTime, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Email(Base):
    """一封 LKML 邮件，主键为 RFC822 Message-ID。"""

    __tablename__ = "emails"

    message_id: Mapped[str] = mapped_column(String(512), primary_key=True)
    in_reply_to: Mapped[Optional[str]] = mapped_column(String(512), index=True, nullable=True)
    subject: Mapped[str] = mapped_column(String(1024), nullable=False)
    author: Mapped[str] = mapped_column(String(255), nullable=False)
    date: Mapped[datetime] = mapped_column(DateTime, index=True, nullable=False)
    body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    patch_id: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)
    refs: Mapped[Optional[List[str]]] = mapped_column(JSON, default=list)
    is_patch: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    subsystem: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)
    raw_mbox_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    reply_count: Mapped[int] = mapped_column(Integer, default=0)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Email message_id={self.message_id!r} subject={self.subject!r}>"
