"""认证路由：登录、刷新、当前用户。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.core.security import (
    create_access_token,
    create_refresh_token,
    verify_password,
    verify_token,
)
from app.models.user import User
from app.schemas.auth import LoginRequest, MeRead, RefreshRequest, Token

router = APIRouter()


@router.post("/login", response_model=Token)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)) -> Token:
    """用户名 + 密码登录，返回 JWT。"""
    result = await db.execute(select(User).where(User.username == payload.username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is disabled",
        )
    access = create_access_token(user.id, extra={"role": user.role, "username": user.username})
    refresh = create_refresh_token(user.id)
    return Token(access_token=access, refresh_token=refresh, token_type="bearer")


@router.post("/refresh", response_model=Token)
async def refresh(payload: RefreshRequest, db: AsyncSession = Depends(get_db)) -> Token:
    """使用 refresh token 换取新的 access token。"""
    data = verify_token(payload.refresh_token, expected_type="refresh")
    if not data or "sub" not in data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )
    try:
        user_id = int(data["sub"])
    except (TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or disabled")
    access = create_access_token(user.id, extra={"role": user.role, "username": user.username})
    return Token(access_token=access, token_type="bearer")


@router.get("/me", response_model=MeRead)
async def me(current_user: User = Depends(get_current_user)) -> MeRead:
    return MeRead.model_validate(current_user)
