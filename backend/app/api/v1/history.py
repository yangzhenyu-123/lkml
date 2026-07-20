"""历史分析作业路由：创建、查询、详情、重试、WebSocket 流。"""
from __future__ import annotations

import asyncio
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import get_current_user, get_db, require_analyst
from app.core.websocket_manager import ws_manager
from app.models.analysis import AnalysisJob, JobItem, StageRecord
from app.models.user import User
from app.schemas.analysis import (
    AnalysisJobCreate,
    AnalysisJobDetail,
    AnalysisJobList,
    AnalysisJobRead,
    JobCreateResponse,
    JobItemRead,
    RetryResponse,
    StageRecordRead,
)
from app.workers.tasks import retry_stage_item_task, run_pipeline_task

router = APIRouter()


@router.post("/jobs", response_model=JobCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_job(
    payload: AnalysisJobCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_analyst),
) -> JobCreateResponse:
    """创建分析作业并触发流水线。"""
    if payload.year_end < payload.year_start:
        raise HTTPException(status_code=400, detail="year_end must be >= year_start")
    job = AnalysisJob(
        name=payload.name,
        year_start=payload.year_start,
        year_end=payload.year_end,
        subsystem_filter=payload.subsystem_filter,
        keyword_filter=payload.keyword_filter,
        status="pending",
        current_stage=0,
        created_by=current_user.id,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    # 创建 4 条阶段占位记录
    for stage_no in range(1, 5):
        db.add(StageRecord(job_id=job.id, stage_no=stage_no, status="pending"))
    await db.commit()

    try:
        task = run_pipeline_task.delay(job.id)
    except Exception as exc:  # noqa: BLE001
        job.status = "failed"
        job.error_message = f"enqueue failed: {exc}"
        await db.commit()
        raise HTTPException(status_code=503, detail=f"Failed to enqueue: {exc}")

    return JobCreateResponse(job_id=job.id, task_id=task.id, status="queued")


@router.get("/jobs", response_model=AnalysisJobList)
async def list_jobs(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    status_filter: Optional[str] = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> AnalysisJobList:
    stmt = select(AnalysisJob)
    count_stmt = select(func.count()).select_from(AnalysisJob)
    if status_filter:
        stmt = stmt.where(AnalysisJob.status == status_filter)
        count_stmt = count_stmt.where(AnalysisJob.status == status_filter)
    total = (await db.execute(count_stmt)).scalar_one()
    stmt = stmt.order_by(AnalysisJob.id.desc()).offset(skip).limit(limit)
    rows = (await db.execute(stmt)).scalars().all()
    return AnalysisJobList(
        total=total,
        skip=skip,
        limit=limit,
        items=[AnalysisJobRead.model_validate(r) for r in rows],
    )


@router.get("/jobs/{job_id}", response_model=AnalysisJobDetail)
async def get_job_detail(
    job_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> AnalysisJobDetail:
    job = (
        await db.execute(select(AnalysisJob).where(AnalysisJob.id == job_id))
    ).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    stages = (
        await db.execute(
            select(StageRecord).where(StageRecord.job_id == job_id).order_by(StageRecord.stage_no)
        )
    ).scalars().all()
    items = (
        await db.execute(
            select(JobItem).where(JobItem.job_id == job_id).order_by(JobItem.stage_no, JobItem.id)
        )
    ).scalars().all()
    return AnalysisJobDetail(
        **AnalysisJobRead.model_validate(job).model_dump(),
        stages=[StageRecordRead.model_validate(s) for s in stages],
        items=[JobItemRead.model_validate(i) for i in items],
    )


@router.post("/jobs/{job_id}/stages/{stage_no}/items/{item_id}/retry", response_model=RetryResponse)
async def retry_item(
    job_id: int,
    stage_no: int,
    item_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_analyst),
) -> RetryResponse:
    """重试某 stage 的某个 item：创建新版本（version+1）并触发任务。"""
    if stage_no not in (3, 4):
        raise HTTPException(status_code=400, detail="Only stage 3 or 4 items can be retried")

    old = (
        await db.execute(
            select(JobItem).where(
                JobItem.id == item_id,
                JobItem.job_id == job_id,
                JobItem.stage_no == stage_no,
            )
        )
    ).scalar_one_or_none()
    if not old:
        raise HTTPException(status_code=404, detail="Item not found")

    new = JobItem(
        job_id=job_id,
        stage_no=stage_no,
        parent_item_id=old.id,
        title=old.title,
        email_message_id=old.email_message_id,
        patch_id=old.patch_id,
        author=old.author,
        subsystem=old.subsystem,
        optimization_type=old.optimization_type,
        merged_upstream=old.merged_upstream,
        status="retrying",
        version=old.version + 1,
    )
    db.add(new)
    # 标记旧 item 为 failed（保留历史）
    old.status = "failed"
    await db.commit()
    await db.refresh(new)

    try:
        task = retry_stage_item_task.delay(new.id)
    except Exception as exc:  # noqa: BLE001
        new.status = "failed"
        new.error_message = f"enqueue failed: {exc}"
        await db.commit()
        raise HTTPException(status_code=503, detail=f"Failed to enqueue retry: {exc}")

    return RetryResponse(
        old_item_id=old.id,
        new_item_id=new.id,
        version=new.version,
        task_id=task.id,
        status="queued",
    )


@router.websocket("/jobs/{job_id}/stream")
async def job_stream(ws: WebSocket, job_id: int) -> None:
    """WebSocket 端点：推送某 job 的 stage/item 状态变更。"""
    await ws_manager.connect(job_id, ws)
    try:
        # 主动发送一次连接确认
        await ws.send_text(f'{{"type":"connected","job_id":{job_id}}}')
        # 保持连接，等待后端 publish 推送；同时消费 ping
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await ws_manager.disconnect(job_id, ws)
