from sqlalchemy import select
from sqlalchemy.orm import Session

from app.features.auth.application.audit_service import add_event
from app.features.auth.application.session_service import revoke_all
from app.features.auth.domain.model import ApplicationGrant
from app.features.users.application.service import get_user


def set_application_grant(
    db: Session,
    *,
    actor_user_id: int,
    user_id: int,
    application: str,
    enabled: bool,
) -> ApplicationGrant:
    user = get_user(db, user_id)
    grant = db.scalar(
        select(ApplicationGrant).where(
            ApplicationGrant.user_id == user.id,
            ApplicationGrant.application == application,
        )
    )
    if grant is None:
        grant = ApplicationGrant(
            user_id=user.id, application=application, enabled=enabled
        )
        db.add(grant)
    else:
        grant.enabled = enabled
    add_event(
        db,
        action="authorization.application_grant_changed",
        entity_type="application_grant",
        actor_user_id=actor_user_id,
        target_user_id=user.id,
        entity_id=application,
        metadata={"enabled": enabled},
    )
    db.commit()
    db.refresh(grant)
    if not enabled:
        revoke_all(db, user.id)
    return grant


def get_application_grants(db: Session, user_id: int) -> list[ApplicationGrant]:
    return list(
        db.scalars(
            select(ApplicationGrant)
            .where(ApplicationGrant.user_id == user_id)
            .order_by(ApplicationGrant.application)
        ).all()
    )
