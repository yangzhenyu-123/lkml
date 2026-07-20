"""SQLAlchemy 声明式基类。

所有 model 都继承自 `Base`，alembic 通过 `Base.metadata` 收集表定义。
"""
from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """项目统一的 ORM 基类。"""

    pass
