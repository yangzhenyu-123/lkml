"""应用配置：基于 pydantic-settings 从环境变量加载。

所有可配置项集中在这里，启动时实例化为单例 `settings`。
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """全局配置。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---------- 应用 ----------
    APP_NAME: str = "LKML Patent Platform"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"

    # ---------- 数据库 ----------
    DATABASE_URL: str = (
        "postgresql+asyncpg://lkml:lkml_secret@localhost:35432/lkml_patent"
    )

    # ---------- Redis / Celery ----------
    CELERY_BROKER_URL: str = "redis://localhost:16379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:16379/1"

    # ---------- JWT ----------
    JWT_SECRET: str = "change_me_to_random_long_string"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 默认 1 天

    # ---------- 初始管理员 ----------
    INIT_ADMIN_USERNAME: str = "admin"
    INIT_ADMIN_PASSWORD: str = "admin_change_me"
    INIT_ADMIN_EMAIL: str = "admin@example.com"

    # ---------- LKML ----------
    # 旧的 HTTP mbox 接口已被 lore.kernel.org Anubis 反爬保护拦截，不再使用
    LKML_BASE_URL: str = "https://lore.kernel.org/linux-kernel"
    # git 分片镜像根 URL：每个分片是一个 ~1GB 的 bare git 仓库
    # URL 形如 https://lore.kernel.org/lkml/{0..N}，分片 0=最旧，N=最新
    LKML_GIT_BASE: str = "https://lore.kernel.org/lkml"
    # 探测分片数量时的最大重试次数与超时
    LKML_PROBE_TIMEOUT: int = 20

    # ---------- 路径 ----------
    KERNEL_MIRROR_PATH: str = "/data/kernel-mirror"
    # git 分片镜像本地目录（每个分片克隆为 lkml-{N}.git bare 仓库）
    LKML_MIRROR_PATH: str = "/data/lkml-mirror"
    # 保留以兼容旧 .env，但代码不再使用
    LKML_MBOX_PATH: str = "/data/lkml-mbox"
    OUTPUTS_PATH: str = "/data/outputs"
    OPENCODE_CONFIG_PATH: str = "/data/opencode-config"

    # ---------- OpenCode ----------
    OPENCODE_API_BASE: str = "https://api.openai.com/v1"
    OPENCODE_API_KEY: str = ""
    OPENCODE_MODEL: str = "gpt-4o"
    OPENCODE_TIMEOUT: int = 600
    OPENCODE_MAX_TOKENS: int = 8192

    # ---------- AES 加密 ----------
    # 用于加密存储用户 OpenAI API key 等敏感字段
    AES_SECRET_KEY: str = "lkml_patent_aes_key_change_me_32b!"

    # ---------- SMTP ----------
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM: Optional[str] = None
    SMTP_USE_TLS: bool = True

    # ---------- CORS ----------
    CORS_ORIGINS: List[str] = Field(default_factory=lambda: ["*"])

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _split_cors(cls, v: Any) -> Any:
        if isinstance(v, str):
            return [item.strip() for item in v.split(",") if item.strip()]
        return v

    # ---------- 便捷属性 ----------
    @property
    def sync_database_url(self) -> str:
        """供 alembic / 同步脚本使用的 psycopg2 URL。"""
        url = self.DATABASE_URL
        if "+asyncpg" in url:
            return url.replace("+asyncpg", "+psycopg2")
        return url

    @property
    def lkml_mbox_dir(self) -> Path:
        p = Path(self.LKML_MBOX_PATH)
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def lkml_mirror_dir(self) -> Path:
        """git 分片镜像目录（每个分片克隆为 lkml-{N}.git bare 仓库）。"""
        p = Path(self.LKML_MIRROR_PATH)
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def outputs_dir(self) -> Path:
        p = Path(self.OUTPUTS_PATH)
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def opencode_config_dir(self) -> Path:
        p = Path(self.OPENCODE_CONFIG_PATH)
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def kernel_mirror_dir(self) -> Path:
        return Path(self.KERNEL_MIRROR_PATH)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
