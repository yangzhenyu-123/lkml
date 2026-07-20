"""订阅路由：当前用户增删查、退订（无需认证）。"""
from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.subscription import Subscription
from app.models.user import User
from app.schemas.subscription import (
    SubscriptionCreate,
    SubscriptionList,
    SubscriptionRead,
    UnsubscribeResponse,
)

router = APIRouter()


@router.get("", response_model=SubscriptionList)
async def list_my_subscriptions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SubscriptionList:
    rows = (
        await db.execute(
            select(Subscription).where(Subscription.user_id == current_user.id).order_by(Subscription.id)
        )
    ).scalars().all()
    return SubscriptionList(total=len(rows), items=[SubscriptionRead.model_validate(r) for r in rows])


@router.post("", response_model=SubscriptionRead, status_code=status.HTTP_201_CREATED)
async def create_subscription(
    payload: SubscriptionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SubscriptionRead:
    sub = Subscription(
        user_id=current_user.id,
        type=payload.type,
        subsystem_filter=payload.subsystem_filter,
        email_notify=payload.email_notify,
        unsubscribe_token=secrets.token_urlsafe(24),
    )
    db.add(sub)
    await db.commit()
    await db.refresh(sub)
    return SubscriptionRead.model_validate(sub)


@router.delete("/{sub_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_subscription(
    sub_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    sub = (
        await db.execute(select(Subscription).where(Subscription.id == sub_id))
    ).scalar_one_or_none()
    if not sub or sub.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Subscription not found")
    await db.delete(sub)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/unsubscribe/{token}", response_model=UnsubscribeResponse)
async def unsubscribe(
    token: str,
    db: AsyncSession = Depends(get_db),
) -> UnsubscribeResponse:
    sub = (
        await db.execute(
            select(Subscription).where(Subscription.unsubscribe_token == token)
        )
    ).scalar_one_or_none()
    if not sub:
        return UnsubscribeResponse(ok=False, message="Invalid or expired token")
    await db.delete(sub)
    await db.commit()
    return UnsubscribeResponse(ok=True, message="Unsubscribed successfully")
