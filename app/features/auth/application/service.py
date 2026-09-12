from sqlalchemy.orm import Session

from app.core.security import dummy_password_hash, verify_password
from app.features.user.application.service import get_user_by_username
from app.features.user.domain.model import User


def authenticate_user(db: Session, *, username: str, password: str) -> User | None:
    user = get_user_by_username(db, username)
    if user is None:
        verify_password(password, dummy_password_hash)
        return None
    return user if verify_password(password, user.password_hash) else None
