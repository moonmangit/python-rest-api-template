from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.features.users.domain.model import User, UserRole


class UserAlreadyExistsError(Exception):
    """Raised when a user email is already registered."""


class InvalidUserError(ValueError):
    """Raised when a user violates a domain invariant."""


class UserNotFoundError(LookupError):
    """Raised when a requested user does not exist."""


class LastAdminError(ValueError):
    """Raised when an operation would remove the final administrator."""


class GoogleIdentityConflictError(ValueError):
    """Raised when a Google identity and email belong to different users."""


def list_users(db: Session) -> list[User]:
    return list(db.scalars(select(User).order_by(User.id)).all())


def get_user(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise UserNotFoundError
    return user


def create_user(
    db: Session,
    *,
    name: str,
    email: str,
    role: UserRole = UserRole.USER,
) -> User:
    normalized_name = name.strip()
    if not normalized_name:
        raise InvalidUserError("User name cannot be empty")

    normalized_email = email.strip().lower()
    existing_user = db.scalar(select(User).where(User.email == normalized_email))
    if existing_user is not None:
        raise UserAlreadyExistsError

    new_user = User(name=normalized_name, email=normalized_email, role=role)
    db.add(new_user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise UserAlreadyExistsError from exc

    db.refresh(new_user)
    return new_user


def update_user(
    db: Session,
    user_id: int,
    *,
    name: str | None = None,
    email: str | None = None,
    role: UserRole | None = None,
) -> User:
    user = get_user(db, user_id)
    if name is not None:
        normalized_name = name.strip()
        if not normalized_name:
            raise InvalidUserError("User name cannot be empty")
        user.name = normalized_name
    if email is not None:
        normalized_email = email.strip().lower()
        existing_user = db.scalar(
            select(User).where(User.email == normalized_email, User.id != user_id)
        )
        if existing_user is not None:
            raise UserAlreadyExistsError
        user.email = normalized_email
    if role is not None and role != user.role:
        _ensure_admin_remains(db, user, role)
        user.role = role

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise UserAlreadyExistsError from exc
    db.refresh(user)
    return user


def delete_user(db: Session, user_id: int) -> None:
    user = get_user(db, user_id)
    _ensure_admin_remains(db, user, None)
    db.delete(user)
    db.commit()


def authenticate_google_user(
    db: Session,
    *,
    google_subject: str,
    name: str,
    email: str,
) -> User:
    normalized_email = email.strip().lower()
    normalized_name = name.strip() or normalized_email.split("@", 1)[0]
    normalized_name = normalized_name[:100]

    subject_user = db.scalar(select(User).where(User.google_subject == google_subject))
    email_user = db.scalar(select(User).where(User.email == normalized_email))
    user: User | None = None
    if subject_user is not None and email_user is not None:
        if subject_user.id != email_user.id:
            raise GoogleIdentityConflictError
        user = subject_user
    elif subject_user is not None:
        user = subject_user
    else:
        user = email_user

    if user is not None and user.google_subject not in (None, google_subject):
        raise GoogleIdentityConflictError

    if user is None:
        # PostgreSQL advisory locking serializes the first-account decision.
        if db.get_bind().dialect.name == "postgresql":
            db.execute(select(func.pg_advisory_xact_lock(738291)))
        has_users = db.scalar(select(func.count()).select_from(User))
        user = User(
            name=normalized_name,
            email=normalized_email,
            google_subject=google_subject,
            role=UserRole.ADMIN if has_users == 0 else UserRole.USER,
        )
        db.add(user)
    else:
        user.google_subject = google_subject
        user.name = normalized_name
        user.email = normalized_email

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        concurrent_user = db.scalar(
            select(User).where(User.google_subject == google_subject)
        )
        if concurrent_user is not None:
            return concurrent_user
        raise UserAlreadyExistsError from exc
    db.refresh(user)
    return user


def _ensure_admin_remains(
    db: Session, user: User, replacement_role: UserRole | None
) -> None:
    if user.role != UserRole.ADMIN:
        return
    if replacement_role == UserRole.ADMIN:
        return
    admin_count = db.scalar(
        select(func.count()).select_from(User).where(User.role == UserRole.ADMIN)
    )
    if admin_count == 1:
        raise LastAdminError
