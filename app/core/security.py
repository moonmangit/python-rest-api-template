import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import settings


def create_access_token(user_id: int, session_id: str | None = None) -> str:
    key = _jwt_key()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
        "iss": settings.app_name,
    }
    if session_id is not None:
        payload["sid"] = session_id
    return jwt.encode(payload, key, algorithm="HS256")


def decode_access_token(token: str) -> int | None:
    payload = decode_access_claims(token)
    if payload is None:
        return None
    user_id = payload.get("sub")
    if not isinstance(user_id, str) or not user_id.isdigit():
        return None
    return int(user_id)


def decode_access_claims(token: str) -> dict | None:
    if not token:
        return None
    try:
        payload = jwt.decode(
            token,
            _jwt_key(),
            algorithms=["HS256"],
            issuer=settings.app_name,
            options={"require": ["sub", "iat", "exp", "iss"]},
        )
        return payload
    except (jwt.InvalidTokenError, RuntimeError):
        return None


def set_auth_cookie(response, token: str) -> None:
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=token,
        max_age=settings.jwt_expire_minutes * 60,
        httponly=True,
        secure=settings.environment == "production",
        samesite="lax",
        path="/",
    )


def set_refresh_cookie(response, token: str) -> None:
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=token,
        max_age=settings.refresh_expire_days * 24 * 60 * 60,
        httponly=True,
        secure=settings.environment == "production",
        samesite="lax",
        path="/api/v1/auth",
    )


def set_csrf_cookie(response, token: str | None = None) -> str:
    token = token or secrets.token_urlsafe(32)
    response.set_cookie(
        key=settings.csrf_cookie_name,
        value=token,
        max_age=settings.refresh_expire_days * 24 * 60 * 60,
        httponly=False,
        secure=settings.environment == "production",
        samesite="lax",
        path="/",
    )
    return token


def clear_auth_cookie(response) -> None:
    response.delete_cookie(
        key=settings.auth_cookie_name,
        httponly=True,
        secure=settings.environment == "production",
        samesite="lax",
        path="/",
    )
    response.delete_cookie(
        key=settings.refresh_cookie_name,
        httponly=True,
        secure=settings.environment == "production",
        samesite="lax",
        path="/api/v1/auth",
    )
    response.delete_cookie(
        key=settings.csrf_cookie_name,
        httponly=False,
        secure=settings.environment == "production",
        samesite="lax",
        path="/",
    )


def new_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _jwt_key() -> str:
    if len(settings.jwt_secret_key) < 32:
        raise RuntimeError("JWT_SECRET_KEY must be at least 32 characters")
    return settings.jwt_secret_key
