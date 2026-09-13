import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_refresh_token, new_refresh_token
from app.features.auth.application.audit_service import add_event
from app.features.auth.domain.model import RefreshSession


class RefreshSessionError(ValueError):
    """Raised when a refresh token is invalid, expired, or revoked."""


def create_session(
    db: Session,
    user_id: int,
    *,
    user_agent: str | None = None,
    ip_address: str | None = None,
) -> tuple[str, str, RefreshSession]:
    now = datetime.now(timezone.utc)
    refresh_token = new_refresh_token()
    session = RefreshSession(
        id=secrets.token_urlsafe(24),
        user_id=user_id,
        token_hash=hash_refresh_token(refresh_token),
        expires_at=now + timedelta(days=settings.refresh_expire_days),
        user_agent=user_agent[:512] if user_agent else None,
        ip_address=ip_address[:64] if ip_address else None,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session.id, refresh_token, session


def rotate_session(
    db: Session,
    refresh_token: str,
    *,
    user_agent: str | None = None,
    ip_address: str | None = None,
) -> tuple[str, str, RefreshSession]:
    now = datetime.now(timezone.utc)
    session = db.scalar(
        select(RefreshSession)
        .where(RefreshSession.token_hash == hash_refresh_token(refresh_token))
        .with_for_update()
    )
    if session is None:
        raise RefreshSessionError
    if session.revoked_at is not None:
        if session.replaced_by_id is not None:
            revoke_all(db, session.user_id, reason="refresh_reuse")
        raise RefreshSessionError
    if _as_utc(session.expires_at) <= now:
        session.revoked_at = now
        db.commit()
        raise RefreshSessionError

    new_id = secrets.token_urlsafe(24)
    new_token = new_refresh_token()
    replacement = RefreshSession(
        id=new_id,
        user_id=session.user_id,
        token_hash=hash_refresh_token(new_token),
        expires_at=now + timedelta(days=settings.refresh_expire_days),
        user_agent=user_agent[:512] if user_agent else None,
        ip_address=ip_address[:64] if ip_address else None,
    )
    db.add(replacement)
    # Ensure the self-referencing replacement exists before linking the old row.
    db.flush()
    session.revoked_at = now
    session.replaced_by_id = new_id
    session.last_used_at = now
    db.commit()
    return new_id, new_token, replacement


def revoke_token(
    db: Session,
    refresh_token: str | None,
    *,
    actor_user_id: int | None = None,
    reason: str = "logout",
) -> None:
    if not refresh_token:
        return
    session = db.scalar(
        select(RefreshSession).where(
            RefreshSession.token_hash == hash_refresh_token(refresh_token)
        )
    )
    if session is not None and session.revoked_at is None:
        session.revoked_at = datetime.now(timezone.utc)
        add_event(
            db,
            action="auth.session_revoked",
            entity_type="session",
            actor_user_id=actor_user_id,
            target_user_id=session.user_id,
            entity_id=session.id,
            metadata={"reason": reason},
        )
        db.commit()


def revoke_all(
    db: Session,
    user_id: int,
    *,
    actor_user_id: int | None = None,
    reason: str = "logout_all",
) -> None:
    now = datetime.now(timezone.utc)
    sessions = db.scalars(
        select(RefreshSession).where(
            RefreshSession.user_id == user_id,
            RefreshSession.revoked_at.is_(None),
        )
    ).all()
    for session in sessions:
        session.revoked_at = now
    add_event(
        db,
        action="auth.sessions_revoked",
        entity_type="session",
        actor_user_id=actor_user_id,
        target_user_id=user_id,
        metadata={"reason": reason, "count": len(sessions)},
    )
    db.commit()


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
