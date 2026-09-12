import pytest

from app.core.security import create_access_token
from app.features.todo.domain import Todo
from app.features.user.application.service import create_user


async def login(client, username: str, password: str = "password123") -> None:
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200


@pytest.mark.anyio
async def test_user_can_crud_only_owned_todos(client, db) -> None:
    alice = (
        await client.post(
            "/api/v1/auth/register",
            json={
                "name": "Alice",
                "email": "alice@example.com",
                "username": "alice",
                "password": "password123",
            },
        )
    ).json()
    await client.post(
        "/api/v1/auth/register",
        json={
            "name": "Bob",
            "email": "bob@example.com",
            "username": "bob",
            "password": "password123",
        },
    )

    await login(client, "alice")
    todo = (await client.post("/api/v1/todos/", json={"title": "Buy milk"})).json()
    assert todo["owner_id"] == alice["id"]

    await login(client, "bob")
    assert (await client.get("/api/v1/todos/")).json() == []
    assert (
        await client.patch(f"/api/v1/todos/{todo['id']}", json={"completed": True})
    ).status_code == 404
    assert (await client.delete(f"/api/v1/todos/{todo['id']}")).status_code == 404


@pytest.mark.anyio
async def test_admin_can_manage_users_and_all_todos(client, db) -> None:
    admin = create_user(
        db,
        name="Admin",
        email="admin@example.com",
        username="admin",
        password="password123",
        role="admin",
    )
    user = create_user(
        db,
        name="User",
        email="user@example.com",
        username="user",
        password="password123",
    )
    client.cookies.set("access_token", create_access_token(admin.id))

    created_user = await client.post(
        "/api/v1/users/",
        json={
            "name": "Second User",
            "email": "second@example.com",
            "username": "second",
            "password": "password123",
        },
    )
    assert created_user.status_code == 201
    assert (
        await client.patch(f"/api/v1/users/{user.id}", json={"role": "admin"})
    ).status_code == 200

    todo = await client.post(
        "/api/v1/admin/todos/",
        json={"owner_id": user.id, "title": "Admin task"},
    )
    assert todo.status_code == 201
    assert len((await client.get("/api/v1/admin/todos/")).json()) == 1
    assert (
        await client.delete(f"/api/v1/admin/todos/{todo.json()['id']}")
    ).status_code == 204


@pytest.mark.anyio
async def test_deleting_account_removes_owned_todos(client, db) -> None:
    user = create_user(
        db,
        name="Alice",
        email="alice@example.com",
        username="alice",
        password="password123",
        role="user",
    )
    client.cookies.set("access_token", create_access_token(user.id))
    todo = (await client.post("/api/v1/todos/", json={"title": "Delete me"})).json()

    assert (await client.delete("/api/v1/auth/me")).status_code == 204
    assert db.get(Todo, todo["id"]) is None


@pytest.mark.anyio
async def test_admin_deleting_user_removes_owned_todos(client, db) -> None:
    admin = create_user(
        db,
        name="Admin",
        email="admin@example.com",
        username="admin",
        password="password123",
        role="admin",
    )
    user = create_user(
        db,
        name="User",
        email="user@example.com",
        username="user",
        password="password123",
    )
    client.cookies.set("access_token", create_access_token(admin.id))
    user_todo = (
        await client.post(
            "/api/v1/admin/todos/",
            json={"owner_id": user.id, "title": "Cascade me"},
        )
    ).json()

    assert (await client.delete(f"/api/v1/users/{user.id}")).status_code == 204
    assert db.get(Todo, user_todo["id"]) is None
