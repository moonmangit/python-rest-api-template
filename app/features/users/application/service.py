from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.features.auth.application.audit_service import add_event
from app.features.auth.application.session_service import revoke_all
from app.features.users.domain.model import User, UserRole, UserStatus


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
    role: UserRole = UserRole.MEMBER,
    status: UserStatus = UserStatus.ENABLED,
) -> User:
    normalized_name = name.strip()
    if not normalized_name:
        raise InvalidUserError("User name cannot be empty")

    normalized_email = email.strip().lower()
    existing_user = db.scalar(select(User).where(User.email == normalized_email))
    if existing_user is not None:
        raise UserAlreadyExistsError

    new_user = User(
        name=normalized_name,
        email=normalized_email,
        role=role,
        status=status,
    )
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
    status: UserStatus | None = None,
    actor_user_id: int | None = None,
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
        _ensure_admin_remains(db, user, role, user.status)
        user.role = role
    if status is not None and status != user.status:
        _ensure_admin_remains(db, user, user.role, status)
        user.status = status

    add_event(
        db,
        action="user.updated",
        entity_type="user",
        actor_user_id=actor_user_id,
        target_user_id=user.id,
        entity_id=str(user.id),
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise UserAlreadyExistsError from exc
    db.refresh(user)
    if user.status == UserStatus.DISABLED or user.role == UserRole.GUEST:
        revoke_all(db, user.id)
    return user


def delete_user(db: Session, user_id: int, *, actor_user_id: int | None = None) -> None:
    user = get_user(db, user_id)
    _ensure_admin_remains(db, user, None, None)
    add_event(
        db,
        action="user.deleted",
        entity_type="user",
        actor_user_id=actor_user_id,
        target_user_id=user.id,
        entity_id=str(user.id),
    )
    db.delete(user)
    db.commit()


def ensure_user_deletable(db: Session, user_id: int) -> User:
    user = get_user(db, user_id)
    _ensure_admin_remains(db, user, None, None)
    return user


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
            role=UserRole.ADMIN if has_users == 0 else UserRole.GUEST,
            status=UserStatus.ENABLED,
        )
        db.add(user)
        db.flush()
    else:
        user.google_subject = google_subject
        user.name = normalized_name
        user.email = normalized_email

    add_event(
        db,
        action="auth.google_login",
        entity_type="user",
        target_user_id=user.id,
        entity_id=str(user.id),
    )

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
    db: Session,
    user: User,
    replacement_role: UserRole | None,
    replacement_status: UserStatus | None,
) -> None:
    if user.role != UserRole.ADMIN or user.status != UserStatus.ENABLED:
        return
    if replacement_role == UserRole.ADMIN and replacement_status in (
        None,
        UserStatus.ENABLED,
    ):
        return
    admins = db.scalars(
        select(User.id)
        .where(User.role == UserRole.ADMIN, User.status == UserStatus.ENABLED)
        .with_for_update()
    ).all()
    if len(admins) == 1:
        raise LastAdminError
