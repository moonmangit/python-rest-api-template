from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.features.users.domain.model import User


class UserAlreadyExistsError(Exception):
    """Raised when a user email is already registered."""


class InvalidUserError(ValueError):
    """Raised when a user violates a domain invariant."""


def list_users(db: Session) -> list[User]:
    return list(db.scalars(select(User).order_by(User.id)).all())


def create_user(db: Session, *, name: str, email: str) -> User:
    normalized_name = name.strip()
    if not normalized_name:
        raise InvalidUserError("User name cannot be empty")

    normalized_email = email.strip().lower()
    existing_user = db.scalar(select(User).where(User.email == normalized_email))
    if existing_user is not None:
        raise UserAlreadyExistsError

    new_user = User(name=normalized_name, email=normalized_email)
    db.add(new_user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise UserAlreadyExistsError from exc

    db.refresh(new_user)
    return new_user
