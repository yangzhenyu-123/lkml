"""聚合所有 v1 路由。"""
from fastapi import APIRouter

from app.api.v1 import auth, daily, history, lkml, opencode, stats, subscriptions, users

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(lkml.router, prefix="/lkml", tags=["lkml"])
api_router.include_router(history.router, prefix="/history", tags=["history"])
api_router.include_router(daily.router, prefix="/daily", tags=["daily"])
api_router.include_router(opencode.router, prefix="/opencode", tags=["opencode"])
api_router.include_router(
    subscriptions.router, prefix="/subscriptions", tags=["subscriptions"]
)
api_router.include_router(stats.router, prefix="/stats", tags=["stats"])
