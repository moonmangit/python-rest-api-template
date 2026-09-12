from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import settings


def create_access_token(user_id: int) -> str:
    key = _jwt_key()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
        "iss": settings.app_name,
    }
    return jwt.encode(payload, key, algorithm="HS256")


def decode_access_token(token: str) -> int | None:
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
        user_id = payload.get("sub")
        if not isinstance(user_id, str) or not user_id.isdigit():
            return None
        return int(user_id)
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


def clear_auth_cookie(response) -> None:
    response.delete_cookie(
        key=settings.auth_cookie_name,
        httponly=True,
        secure=settings.environment == "production",
        samesite="lax",
        path="/",
    )


def _jwt_key() -> str:
    if len(settings.jwt_secret_key) < 32:
        raise RuntimeError("JWT_SECRET_KEY must be at least 32 characters")
    return settings.jwt_secret_key
