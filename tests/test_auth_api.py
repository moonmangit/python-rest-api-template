import asyncio

import httpx

from app.core.config import settings
from app.core.security import create_access_token
from app.features.auth.application import session_service
from app.features.users.application.service import create_user
from app.main import app
from app.shared.dependencies import get_db


def test_session_cookie_auth_refresh_and_revocation(db, monkeypatch) -> None:
    user = create_user(db, name="User", email="user@example.com")
    session_id, refresh_token, _ = session_service.create_session(db, user.id)
    monkeypatch.setattr(
        settings, "jwt_secret_key", "test-jwt-secret-32-bytes-long-value"
    )
    app.dependency_overrides[get_db] = lambda: db

    async def exercise() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            client.cookies.set(
                settings.auth_cookie_name, create_access_token(user.id, session_id)
            )
            client.cookies.set(settings.refresh_cookie_name, refresh_token)
            client.cookies.set(settings.csrf_cookie_name, "csrf-token")
            assert (await client.get("/api/v1/auth/me")).status_code == 200

            refreshed = await client.post(
                "/api/v1/auth/refresh",
                headers={"x-csrf-token": "csrf-token"},
            )
            assert refreshed.status_code == 204
            assert (await client.get("/api/v1/auth/me")).status_code == 200

            session_service.revoke_all(db, user.id)
            assert (await client.get("/api/v1/auth/me")).status_code == 401

    try:
        asyncio.run(exercise())
    finally:
        app.dependency_overrides.clear()
