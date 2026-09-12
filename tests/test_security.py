from datetime import datetime, timedelta, timezone

import jwt
from starlette.responses import Response

from app.core.config import settings
from app.core.security import (
    clear_auth_cookie,
    create_access_token,
    decode_access_token,
    set_auth_cookie,
)


def test_access_token_round_trip(monkeypatch) -> None:
    monkeypatch.setattr(
        settings, "jwt_secret_key", "test-jwt-secret-32-bytes-long-value"
    )

    token = create_access_token(42)

    assert decode_access_token(token) == 42
    assert decode_access_token(f"{token}tampered") is None


def test_access_token_requires_a_strong_secret(monkeypatch) -> None:
    monkeypatch.setattr(settings, "jwt_secret_key", "too-short")

    assert decode_access_token("not-a-token") is None
    try:
        create_access_token(42)
    except RuntimeError as exc:
        assert str(exc) == "JWT_SECRET_KEY must be at least 32 characters"
    else:
        raise AssertionError("Expected short JWT secret to be rejected")


def test_expired_access_token_is_rejected(monkeypatch) -> None:
    monkeypatch.setattr(
        settings, "jwt_secret_key", "test-jwt-secret-32-bytes-long-value"
    )
    expired = jwt.encode(
        {
            "sub": "42",
            "iat": datetime.now(timezone.utc) - timedelta(hours=2),
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
            "iss": settings.app_name,
        },
        settings.jwt_secret_key,
        algorithm="HS256",
    )

    assert decode_access_token(expired) is None


def test_auth_cookie_is_http_only_and_can_be_cleared(monkeypatch) -> None:
    monkeypatch.setattr(
        settings, "jwt_secret_key", "test-jwt-secret-32-bytes-long-value"
    )
    response = Response()

    set_auth_cookie(response, create_access_token(42))
    cookie = response.headers["set-cookie"]
    assert "access_token=" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie

    clear_auth_cookie(response)
    assert any(
        b'access_token=""' in value
        for key, value in response.raw_headers
        if key == b"set-cookie"
    )
