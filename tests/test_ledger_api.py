import asyncio
from datetime import date

import httpx

from app.core.config import settings
from app.core.security import create_access_token
from app.features.auth.application import session_service
from app.features.users.application.service import create_user
from app.features.users.domain import UserRole
from app.main import app
from app.shared.dependencies import get_db


def test_ledger_api_enforces_csrf_and_supports_record_report(db, monkeypatch) -> None:
    user = create_user(db, name="Admin", email="admin@example.com", role=UserRole.ADMIN)
    member = create_user(db, name="Member", email="member@example.com")
    user_session_id, _, _ = session_service.create_session(db, user.id)
    member_session_id, _, _ = session_service.create_session(db, member.id)
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
                create_access_token(user.id, user_session_id),
            )
            client.cookies.set(settings.csrf_cookie_name, "csrf-token")

            assert (await client.get("/api/v1/ledger/categories")).status_code == 200
            without_csrf = await client.post(
                "/api/v1/ledger/categories", json={"name": "Food"}
            )
            assert without_csrf.status_code == 403
            invalid = await client.post(
                "/api/v1/ledger/categories",
                json={"name": ""},
                headers={"x-csrf-token": "csrf-token"},
            )
            assert invalid.status_code == 422
            assert invalid.json()["detail"]["code"] == "VALIDATION_ERROR"

            category = await client.post(
                "/api/v1/ledger/categories",
                json={"name": "Food", "category_type": "both"},
                headers={"x-csrf-token": "csrf-token"},
            )
            assert category.status_code == 201
            category_id = category.json()["id"]
            record = await client.post(
                "/api/v1/ledger/records",
                json={
                    "record_type": "expense",
                    "amount_minor": 1250,
                    "record_date": "2026-01-03",
                    "category_id": category_id,
                },
                headers={"x-csrf-token": "csrf-token"},
            )
            assert record.status_code == 201
            report = await client.get(
                "/api/v1/ledger/reports",
                params={
                    "start_date": date(2026, 1, 1).isoformat(),
                    "end_date": date(2026, 1, 31).isoformat(),
                },
            )
            assert report.status_code == 200
            assert report.json()["expense_total"] == 1250

            client.cookies.set(
                settings.auth_cookie_name,
                create_access_token(member.id, member_session_id),
            )
            denied = await client.get("/api/v1/ledger/categories")
            assert denied.status_code == 403
            assert denied.json()["detail"]["code"] == "APP_ACCESS_DISABLED"

            client.cookies.set(
                settings.auth_cookie_name,
                create_access_token(user.id, user_session_id),
            )
            grant = await client.patch(
                f"/api/v1/users/{member.id}/applications/spending_ledger",
                json={"enabled": True},
                headers={"x-csrf-token": "csrf-token"},
            )
            assert grant.status_code == 200

            client.cookies.set(
                settings.auth_cookie_name,
                create_access_token(member.id, member_session_id),
            )
            assert (await client.get("/api/v1/ledger/categories")).status_code == 200

    try:
        asyncio.run(exercise())
    finally:
        app.dependency_overrides.clear()
