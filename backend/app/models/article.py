"""每日技术文章模型。"""
from __future__ import annotations

from datetime import date as date_type, datetime
from typing import List, Optional

from sqlalchemy import Date, DateTime, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DailyArticle(Base):
    """每日精选技术文章。"""

    __tablename__ = "daily_articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[date_type] = mapped_column(Date, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(1024), nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    subsystems: Mapped[Optional[List[str]]] = mapped_column(JSON, default=list)
    email_ids: Mapped[Optional[List[str]]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<DailyArticle id={self.id} date={self.date} title={self.title!r}>"
