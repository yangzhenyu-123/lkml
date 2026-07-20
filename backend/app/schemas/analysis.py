"""分析作业 schema。"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class AnalysisJobCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    year_start: int = Field(..., ge=1991, le=2100)
    year_end: int = Field(..., ge=1991, le=2100)
    subsystem_filter: Optional[str] = None
    keyword_filter: Optional[str] = None


class AnalysisJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    year_start: int
    year_end: int
    subsystem_filter: Optional[str] = None
    keyword_filter: Optional[str] = None
    status: str
    current_stage: int
    created_by: Optional[int] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    error_message: Optional[str] = None


class StageRecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: int
    stage_no: int
    status: str
    total_items: int
    success_items: int
    failed_items: int
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class JobItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: int
    stage_no: int
    parent_item_id: Optional[int] = None
    title: Optional[str] = None
    email_message_id: Optional[str] = None
    patch_id: Optional[str] = None
    author: Optional[str] = None
    subsystem: Optional[str] = None
    optimization_type: Optional[str] = None
    merged_upstream: Optional[bool] = None
    status: str
    version: int
    output_path: Optional[str] = None
    log_path: Optional[str] = None
    error_message: Optional[str] = None
    token_usage: int
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    created_at: datetime


class AnalysisJobDetail(AnalysisJobRead):
    stages: List[StageRecordRead] = []
    items: List[JobItemRead] = []


class AnalysisJobList(BaseModel):
    total: int
    skip: int
    limit: int
    items: List[AnalysisJobRead]


class RetryRequest(BaseModel):
    note: Optional[str] = None


class RetryResponse(BaseModel):
    old_item_id: int
    new_item_id: int
    version: int
    task_id: str
    status: str = "queued"


class JobCreateResponse(BaseModel):
    job_id: int
    task_id: str
    status: str = "queued"
