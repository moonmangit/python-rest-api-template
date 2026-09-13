import pytest

from app.features.users.application.service import (
    GoogleIdentityConflictError,
    authenticate_google_user,
    create_user,
)
from app.features.users.domain import UserRole


def test_first_google_account_is_admin_and_later_accounts_are_guests(db) -> None:
    first = authenticate_google_user(
        db,
        google_subject="google-first",
        name="First User",
        email="FIRST@example.com",
    )
    second = authenticate_google_user(
        db,
        google_subject="google-second",
        name="Second User",
        email="second@example.com",
    )

    assert first.role == UserRole.ADMIN
    assert second.role == UserRole.GUEST


def test_google_login_reuses_existing_identity(db) -> None:
    created = authenticate_google_user(
        db,
        google_subject="google-subject",
        name="Original Name",
        email="person@example.com",
    )

    logged_in = authenticate_google_user(
        db,
        google_subject="google-subject",
        name="Updated Name",
        email="PERSON@example.com",
    )

    assert logged_in.id == created.id
    assert logged_in.name == "Updated Name"
    assert logged_in.email == "person@example.com"


def test_google_login_links_existing_email_account(db) -> None:
    existing = create_user(db, name="Existing User", email="person@example.com")

    logged_in = authenticate_google_user(
        db,
        google_subject="google-subject",
        name="Google Name",
        email="PERSON@example.com",
    )

    assert logged_in.id == existing.id
    assert logged_in.google_subject == "google-subject"


def test_google_identity_and_email_cannot_cross_accounts(db) -> None:
    authenticate_google_user(
        db,
        google_subject="google-first",
        name="First User",
        email="first@example.com",
    )
    create_user(db, name="Second User", email="second@example.com")

    with pytest.raises(GoogleIdentityConflictError):
        authenticate_google_user(
            db,
            google_subject="google-first",
            name="First User",
            email="second@example.com",
        )
