import pytest

from app.core.security import create_access_token
from app.features.user.application.service import create_user


@pytest.mark.anyio
async def test_guest_can_register_and_login_sets_http_only_cookie(client) -> None:
    registration = await client.post(
        "/api/v1/auth/register",
        json={
            "name": "Jane Doe",
            "email": "jane@example.com",
            "username": "jane",
            "password": "password123",
        },
    )
    assert registration.status_code == 201
    assert "password" not in registration.json()
    assert registration.json()["role"] == "admin"

    second_registration = await client.post(
        "/api/v1/auth/register",
        json={
            "name": "John Doe",
            "email": "john@example.com",
            "username": "john",
            "password": "password123",
        },
    )
    assert second_registration.status_code == 201
    assert second_registration.json()["role"] == "user"

    login = await client.post(
        "/api/v1/auth/login",
        json={"username": "jane", "password": "password123"},
    )
    assert login.status_code == 200
    cookie = login.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "samesite=lax" in cookie
    assert (await client.get("/api/v1/auth/me")).json()["username"] == "jane"


@pytest.mark.anyio
async def test_authentication_and_admin_routes_require_valid_role(client, db) -> None:
    assert (await client.get("/api/v1/auth/me")).status_code == 401
    assert (await client.get("/api/v1/users/")).status_code == 401

    user = create_user(
        db,
        name="User",
        email="user@example.com",
        username="user",
        password="password123",
        role="user",
    )
    client.cookies.set("access_token", create_access_token(user.id))
    assert (await client.get("/api/v1/users/")).status_code == 403


@pytest.mark.anyio
async def test_deleted_user_token_is_no_longer_valid(client, db) -> None:
    user = create_user(
        db,
        name="User",
        email="user@example.com",
        username="user",
        password="password123",
        role="user",
    )
    client.cookies.set("access_token", create_access_token(user.id))
    db.delete(user)
    db.commit()

    assert (await client.get("/api/v1/auth/me")).status_code == 401
