"""OpenCode 配置与技能 schema。"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


# ============ OpenCodeConfig ============
class OpenCodeConfigRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    api_base: Optional[str] = None
    api_key_enc: Optional[str] = None
    api_key_set: bool = False  # 不回传真实 key，仅返回是否已设置
    model: Optional[str] = None
    timeout: int
    max_tokens: int
    env_json: Optional[Dict[str, Any]] = None
    prompt_templates: Optional[Dict[str, Any]] = None
    updated_at: datetime


class OpenCodeConfigUpdate(BaseModel):
    api_base: Optional[str] = None
    api_key: Optional[str] = Field(
        None, description="明文 API key，后端会加密存储。设为空串表示不修改。"
    )
    model: Optional[str] = None
    timeout: Optional[int] = Field(None, ge=1, le=7200)
    max_tokens: Optional[int] = Field(None, ge=1, le=200000)
    env_json: Optional[Dict[str, Any]] = None
    prompt_templates: Optional[Dict[str, Any]] = None


# ============ SkillConfig ============
class SkillConfigRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    git_url: Optional[str] = None
    branch: Optional[str] = None
    local_path: Optional[str] = None
    enabled: bool
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class SkillConfigCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    git_url: Optional[str] = None
    branch: Optional[str] = None
    local_path: Optional[str] = None
    enabled: bool = True
    description: Optional[str] = None


class SkillConfigList(BaseModel):
    total: int
    items: list[SkillConfigRead]


# ============ 测试 ============
class OpenCodeTestRequest(BaseModel):
    prompt: str = Field("Hello, please reply with: opencode ok", max_length=4000)


class OpenCodeTestResult(BaseModel):
    ok: bool
    output: str = ""
    error: Optional[str] = None
    duration_ms: int = 0
    token_usage: int = 0
