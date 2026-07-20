"""SMTP 邮件通知。"""
from __future__ import annotations

import asyncio
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Optional

from sqlalchemy import select

from app.core.config import settings
from app.db.session import async_session_factory
from app.models.subscription import Subscription
from app.models.user import User


async def send_subscription_email(user: User, subject: str, body: str) -> bool:
    """向单个用户发送邮件通知。"""
    if not settings.SMTP_HOST or not user.email:
        return False
    msg = MIMEMultipart("alternative")
    msg["From"] = settings.SMTP_FROM or settings.SMTP_USER or "noreply@example.com"
    msg["To"] = user.email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    def _send() -> None:
        if settings.SMTP_USE_TLS:
            server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=30)
            try:
                server.ehlo()
                server.starttls()
                server.ehlo()
                if settings.SMTP_USER and settings.SMTP_PASSWORD:
                    server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.sendmail(msg["From"], [user.email], msg.as_string())
            finally:
                server.quit()
        else:
            server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=30)
            try:
                if settings.SMTP_USER and settings.SMTP_PASSWORD:
                    server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.sendmail(msg["From"], [user.email], msg.as_string())
            finally:
                server.quit()

    try:
        await asyncio.to_thread(_send)
        return True
    except Exception:  # noqa: BLE001
        return False


async def notify_subscribers(event_type: str, payload: dict[str, Any]) -> int:
    """通知所有匹配订阅的用户。

    payload 至少包含 subject / body 字段，可选 subsystem 用于过滤。
    返回成功发送数。
    """
    subsystem = payload.get("subsystem")
    async with async_session_factory() as db:
        stmt = select(Subscription, User).join(User, User.id == Subscription.user_id).where(
            Subscription.type == event_type,
            Subscription.email_notify.is_(True),
        )
        rows = (await db.execute(stmt)).all()
    sent = 0
    for sub, user in rows:
        if subsystem and sub.subsystem_filter:
            allowed = [s.strip() for s in sub.subsystem_filter.split(",") if s.strip()]
            if allowed and subsystem not in allowed:
                continue
        subject = payload.get("subject", f"[LKML Patent Platform] {event_type}")
        body = payload.get("body", "")
        ok = await send_subscription_email(user, subject, body)
        if ok:
            sent += 1
    return sent
