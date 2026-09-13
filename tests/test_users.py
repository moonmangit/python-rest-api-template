import pytest

from app.features.users.application.service import (
    InvalidUserError,
    LastAdminError,
    UserAlreadyExistsError,
    create_user,
    delete_user,
    list_users,
    update_user,
)
from app.features.users.domain import UserRole
from app.features.users.presentation.schemas import UserCreate


def test_create_and_list_users(db) -> None:
    user = create_user(db, name="Jane Doe", email="JANE@example.com")

    assert user.id is not None
    assert user.email == "jane@example.com"
    assert list_users(db) == [user]


def test_duplicate_email_is_rejected(db) -> None:
    create_user(db, name="Jane Doe", email="jane@example.com")

    with pytest.raises(UserAlreadyExistsError):
        create_user(db, name="Another User", email="JANE@example.com")


def test_user_create_validates_email() -> None:
    with pytest.raises(ValueError):
        UserCreate(name="Jane Doe", email="not-an-email")


def test_empty_user_name_is_rejected_by_service(db) -> None:
    with pytest.raises(InvalidUserError):
        create_user(db, name="  ", email="jane@example.com")


def test_admin_can_update_and_delete_regular_users(db) -> None:
    admin = create_user(
        db, name="Admin", email="admin@example.com", role=UserRole.ADMIN
    )
    user = create_user(db, name="Jane Doe", email="jane@example.com")

    updated = update_user(
        db,
        user.id,
        name="Jane Updated",
        email="JANE2@example.com",
        role=UserRole.ADMIN,
    )
    assert updated.name == "Jane Updated"
    assert updated.email == "jane2@example.com"
    assert updated.role == UserRole.ADMIN

    delete_user(db, admin.id)
    assert list_users(db) == [updated]


def test_final_admin_cannot_be_demoted_or_deleted(db) -> None:
    admin = create_user(
        db, name="Admin", email="admin@example.com", role=UserRole.ADMIN
    )

    with pytest.raises(LastAdminError):
        update_user(db, admin.id, role=UserRole.MEMBER)

    with pytest.raises(LastAdminError):
        delete_user(db, admin.id)
