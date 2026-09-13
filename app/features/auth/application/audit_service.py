from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.features.auth.domain.model import AuditEvent


def add_event(
    db: Session,
    *,
    action: str,
    entity_type: str,
    actor_user_id: int | None = None,
    target_user_id: int | None = None,
    entity_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> AuditEvent:
    event = AuditEvent(
        action=action,
        entity_type=entity_type,
        actor_user_id=actor_user_id,
        target_user_id=target_user_id,
        entity_id=entity_id,
        metadata_json=metadata,
    )
    db.add(event)
    return event


def list_events(
    db: Session, *, target_user_id: int | None = None, limit: int = 100
) -> list[AuditEvent]:
    query = select(AuditEvent).order_by(
        AuditEvent.created_at.desc(), AuditEvent.id.desc()
    )
    if target_user_id is not None:
        query = query.where(AuditEvent.target_user_id == target_user_id)
    return list(db.scalars(query.limit(min(max(limit, 1), 100))).all())
