from datetime import datetime, timedelta, timezone

import pytest

from app.core.security import create_access_token, decode_access_claims
from app.features.auth.application import session_service
from app.features.auth.domain.model import RefreshSession
from app.features.users.application.service import create_user


def test_refresh_session_rotates_and_reuse_revokes_the_session_family(db) -> None:
    user = create_user(db, name="User", email="user@example.com")
    session_id, refresh_token, _ = session_service.create_session(db, user.id)

    claims = decode_access_claims(create_access_token(user.id, session_id))
    assert claims["sub"] == str(user.id)
    assert claims["sid"] == session_id

    new_id, new_token, _ = session_service.rotate_session(db, refresh_token)
    assert new_id != session_id
    assert new_token != refresh_token
    with pytest.raises(session_service.RefreshSessionError):
        session_service.rotate_session(db, refresh_token)

    sessions = db.query(RefreshSession).all()
    assert all(session.revoked_at is not None for session in sessions)


def test_expired_refresh_session_is_rejected(db) -> None:
    user = create_user(db, name="User", email="user@example.com")
    _, refresh_token, session = session_service.create_session(db, user.id)
    session.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.commit()

    with pytest.raises(session_service.RefreshSessionError):
        session_service.rotate_session(db, refresh_token)
