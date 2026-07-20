"""FastAPI 应用入口。

- 创建 FastAPI(title="LKML Patent Platform", version="0.1.0")
- CORS 允许所有来源（开发期）
- 挂载 /api/v1 路由
- WS 端点 /api/v1/history/jobs/{job_id}/stream（在 v1/history 中定义）
- 启动事件：初始化默认 admin 账号、OpenCodeConfig 单例、预置 patent-disclosure-skill
- GET /health 健康检查
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import settings

logger = logging.getLogger("app.main")
logging.basicConfig(level=logging.INFO)


async def _init_default_admin() -> None:
    """首次启动时创建默认 admin 账号。"""
    from sqlalchemy import select

    from app.core.security import hash_password
    from app.db.session import async_session_factory
    from app.models.user import User

    async with async_session_factory() as db:
        existing = (
            await db.execute(select(User).where(User.username == settings.INIT_ADMIN_USERNAME))
        ).scalar_one_or_none()
        if existing:
            return
        admin = User(
            username=settings.INIT_ADMIN_USERNAME,
            email=settings.INIT_ADMIN_EMAIL,
            hashed_password=hash_password(settings.INIT_ADMIN_PASSWORD),
            role="admin",
            is_active=True,
        )
        db.add(admin)
        await db.commit()
        logger.info("Default admin user created: %s", admin.username)


async def _init_opencode_config() -> None:
    """初始化 OpenCodeConfig 单例（id=1）。"""
    from sqlalchemy import select

    from app.core.security import encrypt_secret
    from app.db.session import async_session_factory
    from app.models.opencode_config import OpenCodeConfig, SkillConfig

    async with async_session_factory() as db:
        cfg = (
            await db.execute(select(OpenCodeConfig).where(OpenCodeConfig.id == 1))
        ).scalar_one_or_none()
        if cfg is None:
            cfg = OpenCodeConfig(
                id=1,
                api_base=settings.OPENCODE_API_BASE,
                api_key_enc=(
                    encrypt_secret(settings.OPENCODE_API_KEY)
                    if settings.OPENCODE_API_KEY
                    else None
                ),
                model=settings.OPENCODE_MODEL,
                timeout=settings.OPENCODE_TIMEOUT,
                max_tokens=settings.OPENCODE_MAX_TOKENS,
                env_json={},
                prompt_templates={
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
                },
            )
            db.add(cfg)
            await db.commit()
            logger.info("OpenCodeConfig singleton initialized")

        # 预置 patent-disclosure-skill（如果不存在则创建占位记录）
        existing_skill = (
            await db.execute(
                select(SkillConfig).where(SkillConfig.name == "patent-disclosure-skill")
            )
        ).scalar_one_or_none()
        if existing_skill is None:
            skill = SkillConfig(
                name="patent-disclosure-skill",
                git_url=None,  # TODO: 填实际仓库地址
                branch=None,
                local_path=None,
                enabled=True,
                description="Patent disclosure document generation skill",
            )
            db.add(skill)
            await db.commit()
            logger.info("Preset skill 'patent-disclosure-skill' created")

        # 预置 optimization-skill
        opt_skill = (
            await db.execute(
                select(SkillConfig).where(SkillConfig.name == "optimization-skill")
            )
        ).scalar_one_or_none()
        if opt_skill is None:
            db.add(
                SkillConfig(
                    name="optimization-skill",
                    git_url=None,
                    enabled=True,
                    description="Kernel performance optimization proposal skill",
                )
            )
            await db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时初始化默认数据。"""
    try:
        await _init_default_admin()
        await _init_opencode_config()
    except Exception as exc:  # noqa: BLE001
        # 启动初始化失败不阻断 API 启动（例如 DB 尚未就绪时由 docker-compose 重启）
        logger.warning("Startup init failed: %s", exc)
    yield


app = FastAPI(
    title="LKML Patent Platform",
    version=settings.APP_VERSION,
    description="LKML 自动同步 + 历史分析 + 专利挖掘一体化平台",
    lifespan=lifespan,
)

# CORS（开发期允许所有来源）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if "*" in settings.CORS_ORIGINS else settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载 v1 路由（含 WS /history/jobs/{id}/stream）
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/health", tags=["health"])
async def health() -> dict:
    return {"status": "ok", "app": settings.APP_NAME, "version": settings.APP_VERSION}


@app.get("/", tags=["root"])
async def root() -> dict:
    return {"app": settings.APP_NAME, "docs": "/docs", "health": "/health"}
