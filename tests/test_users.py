import pytest

from app.features.users.application.service import (
    InvalidUserError,
    UserAlreadyExistsError,
    create_user,
    list_users,
)
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
