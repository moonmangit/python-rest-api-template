import asyncio

import httpx

from app.core.config import settings
from app.core.security import create_access_token
from app.features.auth.application import session_service
from app.features.auth.domain.model import RefreshSession
from app.features.users.application.service import create_user
from app.features.users.domain import UserRole, UserStatus
from app.main import app
from app.shared.dependencies import get_db


def test_admin_can_manage_status_grants_sessions_and_audit(db, monkeypatch) -> None:
    admin = create_user(
        db, name="Admin", email="admin@example.com", role=UserRole.ADMIN
    )
    member = create_user(db, name="Member", email="member@example.com")
    admin_session_id, _, _ = session_service.create_session(db, admin.id)
    session_id, _, _ = session_service.create_session(db, member.id)
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
                settings.auth_cookie_name,
                create_access_token(admin.id, admin_session_id),
            )
            client.cookies.set(settings.csrf_cookie_name, "csrf-token")
            listed = await client.get(
                "/api/v1/users/", params={"search": "member@example.com"}
            )
            assert listed.status_code == 200
            assert len(listed.json()) == 1

            disabled = await client.patch(
                f"/api/v1/users/{member.id}",
                json={"status": UserStatus.DISABLED.value},
                headers={"x-csrf-token": "csrf-token"},
            )
            assert disabled.status_code == 200
            client.cookies.set(
                settings.auth_cookie_name,
                create_access_token(member.id, session_id),
            )
            assert (await client.get("/api/v1/auth/me")).status_code == 401

            client.cookies.set(
                settings.auth_cookie_name,
                create_access_token(admin.id, admin_session_id),
            )
            enabled = await client.patch(
                f"/api/v1/users/{member.id}",
                json={"status": UserStatus.ENABLED.value},
                headers={"x-csrf-token": "csrf-token"},
            )
            assert enabled.status_code == 200
            grant = await client.patch(
                f"/api/v1/users/{member.id}/applications/spending_ledger",
                json={"enabled": True},
                headers={"x-csrf-token": "csrf-token"},
            )
            assert grant.status_code == 200
            revokable_session_id, _, _ = session_service.create_session(db, member.id)

            client.cookies.set(
                settings.auth_cookie_name,
                create_access_token(member.id, revokable_session_id),
            )
            assert (await client.get("/api/v1/ledger/categories")).status_code == 200

            client.cookies.set(
                settings.auth_cookie_name,
                create_access_token(admin.id, admin_session_id),
            )
            disabled_grant = await client.patch(
                f"/api/v1/users/{member.id}/applications/spending_ledger",
                json={"enabled": False},
                headers={"x-csrf-token": "csrf-token"},
            )
            assert disabled_grant.status_code == 200
            blocked_session_id, _, _ = session_service.create_session(db, member.id)
            client.cookies.set(
                settings.auth_cookie_name,
                create_access_token(member.id, blocked_session_id),
            )
            assert (await client.get("/api/v1/ledger/categories")).status_code == 403

            client.cookies.set(
                settings.auth_cookie_name,
                create_access_token(admin.id, admin_session_id),
            )
            revoke = await client.post(
                f"/api/v1/users/{member.id}/sessions/revoke",
                headers={"x-csrf-token": "csrf-token"},
            )
            assert revoke.status_code == 204
            assert db.get(RefreshSession, revokable_session_id).revoked_at is not None
            audit = await client.get("/api/v1/users/audit")
            assert audit.status_code == 200
            actions = {event["action"] for event in audit.json()}
            assert "user.updated" in actions
            assert "authorization.application_grant_changed" in actions

    try:
        asyncio.run(exercise())
    finally:
        app.dependency_overrides.clear()
