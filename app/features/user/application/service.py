import secrets

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.features.user.domain.model import User


class UserAlreadyExistsError(Exception):
    """Raised when a user email is already registered."""


class InvalidUserError(ValueError):
    """Raised when a user violates a domain invariant."""


class UserNotFoundError(LookupError):
    """Raised when a requested user does not exist."""


class LastAdminError(ValueError):
    """Raised when an operation would remove the last administrator."""


def list_users(db: Session) -> list[User]:
    return list(db.scalars(select(User).order_by(User.id)).all())


def get_user(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise UserNotFoundError
    return user


def get_user_by_username(db: Session, username: str) -> User | None:
    return db.scalar(select(User).where(User.username == username.strip().lower()))


def create_user(
    db: Session,
    *,
    name: str,
    email: str,
    username: str | None = None,
    password: str | None = None,
    role: str | None = None,
) -> User:
    normalized_name = name.strip()
    if not normalized_name:
        raise InvalidUserError("User name cannot be empty")

    normalized_email = email.strip().lower()
    normalized_username = (
        (username or normalized_email.split("@", 1)[0]).strip().lower()
    )
    if not normalized_username:
        raise InvalidUserError("Username cannot be empty")
    if role is None:
        user_count = db.scalar(select(func.count()).select_from(User))
        role = "admin" if user_count == 0 else "user"
    if role not in {"user", "admin"}:
        raise InvalidUserError("Invalid user role")

    existing_user = db.scalar(
        select(User).where(
            (User.email == normalized_email) | (User.username == normalized_username)
        )
    )
    if existing_user is not None:
        raise UserAlreadyExistsError

    new_user = User(
        name=normalized_name,
        email=normalized_email,
        username=normalized_username,
        password_hash=hash_password(password or secrets.token_urlsafe(32)),
        role=role,
    )
    db.add(new_user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise UserAlreadyExistsError from exc

    db.refresh(new_user)
    return new_user


def update_user(db: Session, user_id: int, changes: dict[str, object]) -> User:
    user = get_user(db, user_id)
    if "name" in changes:
        if changes["name"] is None:
            raise InvalidUserError("User name cannot be empty")
        normalized_name = str(changes["name"]).strip()
        if not normalized_name:
            raise InvalidUserError("User name cannot be empty")
        user.name = normalized_name
    if "email" in changes:
        if changes["email"] is None:
            raise InvalidUserError("User email cannot be empty")
        user.email = str(changes["email"]).strip().lower()
    if "username" in changes:
        if changes["username"] is None:
            raise InvalidUserError("Username cannot be empty")
        normalized_username = str(changes["username"]).strip().lower()
        if not normalized_username:
            raise InvalidUserError("Username cannot be empty")
        user.username = normalized_username
    if "password" in changes:
        if changes["password"] is None:
            raise InvalidUserError("Password cannot be empty")
        user.password_hash = hash_password(str(changes["password"]))
    if "role" in changes:
        if changes["role"] is None:
            raise InvalidUserError("User role cannot be empty")
        role = str(changes["role"])
        if role not in {"user", "admin"}:
            raise InvalidUserError("Invalid user role")
        if user.role == "admin" and role == "user":
            admin_count = db.scalar(
                select(func.count()).select_from(User).where(User.role == "admin")
            )
            if admin_count is not None and admin_count <= 1:
                raise LastAdminError
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
    if user.role == "admin":
        admin_count = db.scalar(
            select(func.count()).select_from(User).where(User.role == "admin")
        )
        if admin_count is not None and admin_count <= 1:
            raise LastAdminError
    db.delete(user)
    db.commit()


def ensure_admin(db: Session, *, username: str, password: str) -> User:
    existing_user = get_user_by_username(db, username)
    if existing_user is not None:
        if existing_user.role != "admin":
            existing_user.role = "admin"
            db.commit()
        return existing_user
    return create_user(
        db,
        name=username,
        email=f"{username}@localhost",
        username=username,
        password=password,
        role="admin",
    )
