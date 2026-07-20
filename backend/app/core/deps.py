"""依赖注入：DB 会话、当前用户、角色校验。"""
from __future__ import annotations

from typing import AsyncIterator, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_token
from app.db.session import async_session_factory
from app.models.user import User

# tokenUrl 仅用于 OpenAPI 文档展示，实际登录由 /auth/login 处理
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    """提供异步数据库会话，请求结束自动关闭。"""
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """从 JWT 解析当前用户。"""
    creds_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise creds_exc
    payload = verify_token(token, expected_type="access")
    if not payload or "sub" not in payload:
        raise creds_exc
    try:
        user_id = int(payload["sub"])
    except (TypeError, ValueError):
        raise creds_exc

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise creds_exc
    return user


def require_role(*roles: str):
    """角色校验依赖。用法: Depends(require_role("admin", "analyst"))。"""

    async def _checker(current_user: User = Depends(get_current_user)) -> User:
        if roles and current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires role: {', '.join(roles)}",
            )
        return current_user

    return _checker


# 常用快捷依赖
require_admin = require_role("admin")
require_analyst = require_role("admin", "analyst")
