import secrets
from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import decode_access_claims
from app.features.auth.domain.model import ApplicationGrant, RefreshSession
from app.features.users.domain.model import User, UserRole, UserStatus

SessionDep = Annotated[Session, Depends(get_db)]


def get_current_user(request: Request, db: SessionDep) -> User:
    token = request.cookies.get(settings.auth_cookie_name)
    claims = decode_access_claims(token) if token else None
    user_id = claims.get("sub") if claims else None
    if not isinstance(user_id, str) or not user_id.isdigit():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "AUTH_REQUIRED", "message": "Authentication required"},
        )
    user_id_value = int(user_id)
    session_id = claims.get("sid")
    if not isinstance(session_id, str) or not session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "AUTH_REQUIRED", "message": "Authentication required"},
        )
    session = db.scalar(
        select(RefreshSession).where(
            RefreshSession.id == session_id,
            RefreshSession.user_id == user_id_value,
        )
    )
    if (
        session is None
        or session.revoked_at is not None
        or _as_utc(session.expires_at) <= datetime.now(timezone.utc)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "AUTH_REQUIRED", "message": "Authentication required"},
        )
    user = db.get(User, user_id_value)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "AUTH_REQUIRED", "message": "Authentication required"},
        )
    return user


CurrentUserDep = Annotated[User, Depends(get_current_user)]


def require_admin(user: CurrentUserDep) -> User:
    if user.status != UserStatus.ENABLED or user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "ADMIN_REQUIRED",
                "message": "Administrator access required",
            },
        )
    return user


AdminUserDep = Annotated[User, Depends(require_admin)]


def require_csrf(request: Request) -> None:
    cookie = request.cookies.get(settings.csrf_cookie_name)
    header = request.headers.get("x-csrf-token")
    if not cookie or not header or not secrets.compare_digest(cookie, header):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "CSRF_FAILED", "message": "CSRF validation failed"},
        )


CsrfDep = Annotated[None, Depends(require_csrf)]


def require_spending_ledger_access(user: CurrentUserDep, db: SessionDep) -> User:
    if user.status != UserStatus.ENABLED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "ACCOUNT_DISABLED", "message": "Account is disabled"},
        )
    if user.role == UserRole.ADMIN:
        return user
    if user.role != UserRole.MEMBER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "ACCOUNT_PENDING", "message": "Account is pending"},
        )
    grant = db.scalar(
        select(ApplicationGrant).where(
            ApplicationGrant.user_id == user.id,
            ApplicationGrant.application == "spending_ledger",
            ApplicationGrant.enabled.is_(True),
        )
    )
    if grant is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "APP_ACCESS_DISABLED",
                "message": "Application access is disabled",
            },
        )
    return user


SpendingLedgerUserDep = Annotated[User, Depends(require_spending_ledger_access)]


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
