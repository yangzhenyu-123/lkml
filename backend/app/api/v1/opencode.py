"""OpenCode 配置与技能路由，含测试端点。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_admin
from app.core.security import decrypt_secret, encrypt_secret
from app.models.opencode_config import OpenCodeConfig, SkillConfig
from app.models.user import User
from app.schemas.opencode import (
    OpenCodeConfigRead,
    OpenCodeConfigUpdate,
    OpenCodeTestRequest,
    OpenCodeTestResult,
    SkillConfigCreate,
    SkillConfigList,
    SkillConfigRead,
)
from app.services.opencode_runner import test_connection

router = APIRouter()

_DEFAULT_PROMPT_TEMPLATES = {
    "stage3_optimization": (
        "You are a Linux kernel performance optimization expert. "
        "Based on the following LKML patch proposal, write a concrete optimization "
        "proposal in Markdown with sections: Background, Problem, Proposed Change, "
        "Expected Benefit, Risks, References.\n\nContext:\n{context}"
    ),
    "stage4_patent": (
        "You are a patent engineer. Based on the following optimization proposal, "
        "draft a patent disclosure document in Markdown with sections: Title, Field, "
        "Background, Summary, Detailed Description, Claims, Abstract.\n\nProposal:\n{context}"
    ),
    "daily_digest": (
        "Summarize the following LKML emails into a single technical daily digest "
        "article in Markdown. Group by subsystem.\n\nEmails:\n{context}"
    ),
}


# ============ Config ============
async def _get_or_create_config(db: AsyncSession) -> OpenCodeConfig:
    cfg = (
        await db.execute(select(OpenCodeConfig).where(OpenCodeConfig.id == 1))
    ).scalar_one_or_none()
    if cfg is None:
        from app.core.config import settings

        cfg = OpenCodeConfig(
            id=1,
            api_base=settings.OPENCODE_API_BASE,
            api_key_enc=encrypt_secret(settings.OPENCODE_API_KEY) if settings.OPENCODE_API_KEY else None,
            model=settings.OPENCODE_MODEL,
            timeout=settings.OPENCODE_TIMEOUT,
            max_tokens=settings.OPENCODE_MAX_TOKENS,
            env_json={},
            prompt_templates=dict(_DEFAULT_PROMPT_TEMPLATES),
        )
        db.add(cfg)
        await db.commit()
        await db.refresh(cfg)
    return cfg


def _to_read(cfg: OpenCodeConfig) -> OpenCodeConfigRead:
    return OpenCodeConfigRead(
        id=cfg.id,
        api_base=cfg.api_base,
        api_key_enc=None,
        api_key_set=bool(cfg.api_key_enc),
        model=cfg.model,
        timeout=cfg.timeout,
        max_tokens=cfg.max_tokens,
        env_json=cfg.env_json or {},
        prompt_templates=cfg.prompt_templates or {},
        updated_at=cfg.updated_at,
    )


@router.get("/config", response_model=OpenCodeConfigRead)
async def get_config(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> OpenCodeConfigRead:
    cfg = await _get_or_create_config(db)
    return _to_read(cfg)


@router.put("/config", response_model=OpenCodeConfigRead)
async def update_config(
    payload: OpenCodeConfigUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> OpenCodeConfigRead:
    cfg = await _get_or_create_config(db)
    if payload.api_base is not None:
        cfg.api_base = payload.api_base
    if payload.api_key:  # 非空串才更新
        cfg.api_key_enc = encrypt_secret(payload.api_key)
    if payload.model is not None:
        cfg.model = payload.model
    if payload.timeout is not None:
        cfg.timeout = payload.timeout
    if payload.max_tokens is not None:
        cfg.max_tokens = payload.max_tokens
    if payload.env_json is not None:
        cfg.env_json = payload.env_json
    if payload.prompt_templates is not None:
        cfg.prompt_templates = payload.prompt_templates
    await db.commit()
    await db.refresh(cfg)
    return _to_read(cfg)


# ============ Skills ============
@router.get("/skills", response_model=SkillConfigList)
async def list_skills(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> SkillConfigList:
    rows = (await db.execute(select(SkillConfig).order_by(SkillConfig.id))).scalars().all()
    return SkillConfigList(total=len(rows), items=[SkillConfigRead.model_validate(r) for r in rows])


@router.post("/skills", response_model=SkillConfigRead, status_code=status.HTTP_201_CREATED)
async def create_skill(
    payload: SkillConfigCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> SkillConfigRead:
    existing = (
        await db.execute(select(SkillConfig).where(SkillConfig.name == payload.name))
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Skill name already exists")
    skill = SkillConfig(
        name=payload.name,
        git_url=payload.git_url,
        branch=payload.branch,
        local_path=payload.local_path,
        enabled=payload.enabled,
        description=payload.description,
    )
    db.add(skill)
    await db.commit()
    await db.refresh(skill)
    return SkillConfigRead.model_validate(skill)


@router.delete("/skills/{skill_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_skill(
    skill_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> Response:
    skill = (
        await db.execute(select(SkillConfig).where(SkillConfig.id == skill_id))
    ).scalar_one_or_none()
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    await db.delete(skill)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ============ Test ============
@router.post("/test", response_model=OpenCodeTestResult)
async def test_opencode(
    payload: OpenCodeTestRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> OpenCodeTestResult:
    cfg = await _get_or_create_config(db)
    api_key = decrypt_secret(cfg.api_key_enc) if cfg.api_key_enc else ""
    result = await test_connection(
        prompt=payload.prompt,
        api_base=cfg.api_base or "",
        api_key=api_key,
        model=cfg.model or "",
        timeout=cfg.timeout,
    )
    return result
