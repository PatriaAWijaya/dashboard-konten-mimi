"""Utilitas keamanan: hashing password, token acak, dan JWT."""

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from passlib.context import CryptContext

from app.core.config import get_settings


def _pwd_context() -> CryptContext:
    settings = get_settings()
    return CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=settings.BCRYPT_ROUNDS)


def hash_password(password: str) -> str:
    return _pwd_context().hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _pwd_context().verify(password, password_hash)


def generate_token() -> str:
    """Token acak URL-safe untuk verifikasi email & reset password."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Hash sha256 untuk penyimpanan token di database (token mentah tidak disimpan)."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(user_id: uuid.UUID, is_superadmin: bool) -> str:
    settings = get_settings()
    payload = {
        "sub": str(user_id),
        "sa": bool(is_superadmin),
        "type": "access",
        "iat": _now(),
        "exp": _now() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(user_id: uuid.UUID) -> tuple[str, str, datetime]:
    """Return (token, jti, expires_at)."""
    settings = get_settings()
    jti = uuid.uuid4().hex
    expires_at = _now() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": str(user_id),
        "jti": jti,
        "type": "refresh",
        "iat": _now(),
        "exp": expires_at,
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM), jti, expires_at


def decode_token(token: str, expected_type: str) -> dict:
    """Decode & validasi JWT. Raise ValueError bila tidak valid."""
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise ValueError("Token kedaluwarsa.") from exc
    except jwt.InvalidTokenError as exc:
        raise ValueError("Token tidak valid.") from exc
    if payload.get("type") != expected_type:
        raise ValueError("Tipe token tidak sesuai.")
    if not payload.get("sub"):
        raise ValueError("Token tidak valid.")
    return payload
