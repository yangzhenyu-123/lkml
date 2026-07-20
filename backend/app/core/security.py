"""安全工具：JWT 签发/校验、密码哈希、AES 对称加密（用于加密 API key）。"""
from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from cryptography.fernet import Fernet, InvalidToken
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

# ============ 密码哈希 ============
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(raw: str) -> str:
    return pwd_context.hash(raw)


def verify_password(raw: str, hashed: str) -> bool:
    try:
        return pwd_context.verify(raw, hashed)
    except Exception:  # noqa: BLE001
        return False


# ============ JWT ============
def create_access_token(subject: str | int, extra: Optional[dict] = None) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "iat": now,
        "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        "type": "access",
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(subject: str | int) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(subject),
        "iat": now,
        "exp": now + timedelta(days=30),
        "type": "refresh",
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    """解码 JWT，失败抛出 JWTError。"""
    return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])


def verify_token(token: str, expected_type: str = "access") -> Optional[dict[str, Any]]:
    try:
        payload = decode_token(token)
    except JWTError:
        return None
    if payload.get("type") != expected_type:
        return None
    return payload


# ============ AES 加密 (Fernet) ============
def _derive_fernet_key() -> bytes:
    """从 AES_SECRET_KEY 派生 32 字节 key 并编码为 Fernet 兼容 urlsafe base64。"""
    digest = hashlib.sha256(settings.AES_SECRET_KEY.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def _get_fernet() -> Fernet:
    return Fernet(_derive_fernet_key())


def encrypt_secret(plaintext: str) -> str:
    """加密字符串敏感字段（如 API key）。返回 base64 密文。"""
    if not plaintext:
        return ""
    token = _get_fernet().encrypt(plaintext.encode("utf-8"))
    return token.decode("utf-8")


def decrypt_secret(ciphertext: str) -> str:
    """解密由 encrypt_secret 产生的密文。失败返回空串。"""
    if not ciphertext:
        return ""
    try:
        return _get_fernet().decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except (InvalidToken, ValueError):
        return ""


def encrypt_json(obj: Any) -> str:
    return encrypt_secret(json.dumps(obj, ensure_ascii=False))


def decrypt_json(ciphertext: str) -> Any:
    raw = decrypt_secret(ciphertext)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return None
