"""分析作业模型：Job / StageRecord / JobItem。

四阶段流水线：
- Stage 1: 扫描 LKML 性能优化 patch 邮件 → 创建 JobItem(stage_no=1)
- Stage 2: 检测 Stage 1 item 是否合入上游，未合入的创建 Stage 2 item
- Stage 3: 调用 opencode 生成优化方案 → output_path 指向 .md
- Stage 4: 调用 opencode 生成专利交底书 → output_path 指向 .md + .docx
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AnalysisJob(Base):
    """一次历史分析作业。"""

    __tablename__ = "analysis_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    year_start: Mapped[int] = mapped_column(Integer, nullable=False)
    year_end: Mapped[int] = mapped_column(Integer, nullable=False)
    subsystem_filter: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    keyword_filter: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # pending/running/stage1/stage2/stage3/stage4/completed/failed
    status: Mapped[str] = mapped_column(String(32), default="pending")
    current_stage: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AnalysisJob id={self.id} name={self.name!r} status={self.status!r}>"


class StageRecord(Base):
    """每个 Job 的每个阶段汇总记录。"""

    __tablename__ = "stage_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(
        ForeignKey("analysis_jobs.id", ondelete="CASCADE"), index=True
    )
    stage_no: Mapped[int] = mapped_column(Integer, nullable=False)
    # pending/running/completed/failed
    status: Mapped[str] = mapped_column(String(32), default="pending")
    total_items: Mapped[int] = mapped_column(Integer, default=0)
    success_items: Mapped[int] = mapped_column(Integer, default=0)
    failed_items: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<StageRecord job={self.job_id} stage={self.stage_no} status={self.status!r}>"


class JobItem(Base):
    """阶段内单个条目（提案/优化方案/专利交底书）的状态与产出。"""

    __tablename__ = "job_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(
        ForeignKey("analysis_jobs.id", ondelete="CASCADE"), index=True
    )
    stage_no: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    parent_item_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("job_items.id"), nullable=True
    )
    title: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    email_message_id: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    patch_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    author: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    subsystem: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    optimization_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    merged_upstream: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    # pending/running/success/failed/retrying
    status: Mapped[str] = mapped_column(String(32), default="pending")
    version: Mapped[int] = mapped_column(Integer, default=1)
    output_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    log_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    token_usage: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<JobItem id={self.id} job={self.job_id} stage={self.stage_no} status={self.status!r}>"
