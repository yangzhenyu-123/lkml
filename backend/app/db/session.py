"""异步数据库引擎与会话工厂。"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings


def _ensure_async_driver(url: str) -> str:
    """规范化数据库 URL 为 async 驱动形式。

    容器环境变量可能注入 `postgresql://...`（同步形式），
    而 create_async_engine 需要 `postgresql+asyncpg://`。
    这里自动补全 +asyncpg，避免启动时报错：
        'The asyncio extension requires an async driver to be used.
         The loaded 'psycopg2' is not async.'
    """
    if not url:
        return url
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("postgres://"):
        # SQLAlchemy 1.4 起 postgres:// 已弃用，统一为 postgresql://
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    return url


# 显式关闭 statement cache 以避免 PostgreSQL 16 prepared statement 复用问题
engine = create_async_engine(
    _ensure_async_driver(settings.DATABASE_URL),
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
