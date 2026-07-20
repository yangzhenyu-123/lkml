"""Alembic 迁移环境配置。

- 元数据来源：app.db.base.Base.metadata
- 数据库连接：从 app.core.config.settings.DATABASE_URL 读取（asyncpg 驱动）
- 同时支持同步与异步 URL（自动将 +asyncpg 转换为 psycopg2 形式供 offline/online 使用）
"""
from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool

from alembic import context

# ============ 将项目根目录加入 sys.path，使 alembic CLI 能导入 app 包 ============
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# ============ Alembic 配置对象 ============
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ============ 导入项目元数据 ============
# 必须确保所有 model 模块已被导入，Base.metadata 才能完整收集表定义。
from app.core.config import settings  # noqa: E402
from app.db.base import Base  # noqa: E402

# 显式导入所有模型，确保 metadata 注册
from app.models import user, email, analysis, article, subscription, opencode_config  # noqa: E402,F401

target_metadata = Base.metadata

# ============ 从 settings 注入数据库 URL ============
# alembic 使用同步驱动，将 +asyncpg 替换为 +psycopg2
_sync_url = settings.DATABASE_URL
if "+asyncpg" in _sync_url:
    _sync_url = _sync_url.replace("+asyncpg", "+psycopg2")
elif _sync_url.startswith("postgresql://") and "+psycopg2" not in _sync_url:
    # 默认 postgresql:// 也是 psycopg2 兼容
    pass

config.set_main_option("sqlalchemy.url", os.environ.get("ALEMBIC_DATABASE_URL", _sync_url))


def run_migrations_offline() -> None:
    """离线模式：仅生成 SQL，不连接数据库。"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """在线模式：连接数据库执行迁移。"""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
