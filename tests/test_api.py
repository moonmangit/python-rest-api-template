import asyncio

import httpx

from app.core.config import settings
from app.core.security import create_access_token
from app.features.auth.application import session_service
from app.features.users.application.service import create_user
from app.features.users.domain import UserRole
from app.main import app
from app.shared.dependencies import get_db, require_admin


def test_openapi_contains_current_api() -> None:
    paths = app.openapi()["paths"]

    assert "/" in paths
    assert "/api/v1/users/" in paths
    assert "/health/live" in paths
    assert "/health/ready" in paths


def test_user_routes_require_admin_and_support_crud(db, monkeypatch) -> None:
    admin = create_user(
        db, name="Admin", email="admin@example.com", role=UserRole.ADMIN
    )
    session_id, _, _ = session_service.create_session(db, admin.id)
    monkeypatch.setattr(
        settings, "jwt_secret_key", "test-jwt-secret-32-bytes-long-value"
    )
    app.dependency_overrides[get_db] = lambda: db

    async def exercise_routes() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            assert (await client.get("/api/v1/users/")).status_code == 401
            client.cookies.set(
                settings.auth_cookie_name, create_access_token(admin.id, session_id)
            )
            client.cookies.set(settings.csrf_cookie_name, "csrf-token")
            authenticated = await client.get("/api/v1/auth/me")
            assert authenticated.status_code == 200
            assert authenticated.json()["email"] == "admin@example.com"
            client.cookies.set(settings.auth_cookie_name, "invalid-token")
            assert (await client.get("/api/v1/auth/me")).status_code == 401
            app.dependency_overrides[require_admin] = lambda: admin

            created = await client.post(
                "/api/v1/users/",
                json={"name": "Jane Doe", "email": "jane@example.com"},
                headers={"x-csrf-token": "csrf-token"},
            )
            assert created.status_code == 201
            user_id = created.json()["id"]

            fetched = await client.get(f"/api/v1/users/{user_id}")
            assert fetched.status_code == 200
            assert fetched.json()["role"] == "member"

            updated = await client.patch(
                f"/api/v1/users/{user_id}",
                json={"name": "Jane Updated", "role": "admin"},
                headers={"x-csrf-token": "csrf-token"},
            )
            assert updated.status_code == 200
            assert updated.json()["name"] == "Jane Updated"

            deleted = await client.delete(
                f"/api/v1/users/{user_id}",
                headers={"x-csrf-token": "csrf-token"},
            )
            assert deleted.status_code == 204
            assert (await client.get(f"/api/v1/users/{user_id}")).status_code == 404

    try:
        asyncio.run(exercise_routes())
    finally:
        app.dependency_overrides.clear()
