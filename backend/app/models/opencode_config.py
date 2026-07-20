"""OpenCode 配置模型。

OpenCodeConfig: 单例（id 恒为 1），存储 api_base、加密的 api_key、模型、超时、
max_tokens、env_json、prompt_templates 等。
SkillConfig: 多条技能配置，每条对应一个 git 仓库（如 patent-disclosure-skill）。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class OpenCodeConfig(Base):
    """OpenCode 全局配置（单例，id=1）。"""

    __tablename__ = "opencode_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    api_base: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    api_key_enc: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    model: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    timeout: Mapped[int] = mapped_column(Integer, default=600)
    max_tokens: Mapped[int] = mapped_column(Integer, default=8192)
    env_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, default=dict)
    prompt_templates: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON, default=dict
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<OpenCodeConfig id={self.id} model={self.model!r}>"


class SkillConfig(Base):
    """单个 opencode 技能配置（git 仓库）。"""

    __tablename__ = "skill_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    git_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    branch: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    local_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<SkillConfig id={self.id} name={self.name!r} enabled={self.enabled}>"
