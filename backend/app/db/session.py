"""异步数据库引擎与会话工厂。"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

# 显式关闭 statement cache 以避免 PostgreSQL 16 prepared statement 复用问题
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    future=True,
)

async_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    autoflush=False,
    class_=AsyncSession,
)


async def get_async_session() -> AsyncSession:
    """便捷获取会话（不作为 FastAPI 依赖使用，依赖见 core.deps.get_db）。"""
    async with async_session_factory() as session:
        return session
