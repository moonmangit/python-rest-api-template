from datetime import date

import pytest
from fastapi import HTTPException

from app.features.auth.application import (
    audit_service,
    authorization_service,
    session_service,
)
from app.features.auth.domain.model import AuditEvent, RefreshSession
from app.features.spending_ledger.application import service as ledger_service
from app.features.spending_ledger.domain import CategoryType, LedgerRecord, RecordType
from app.features.spending_ledger.domain.model import (
    Attachment,
)
from app.features.users.application.service import (
    LastAdminError,
    authenticate_google_user,
    create_user,
    delete_user,
    ensure_user_deletable,
    update_user,
)
from app.features.users.domain import User, UserRole, UserStatus
from app.shared.dependencies import require_spending_ledger_access


def test_guest_approval_demotion_and_application_grant_lifecycle(db) -> None:
    admin = authenticate_google_user(
        db,
        google_subject="admin-subject",
        name="Admin",
        email="admin@example.com",
    )
    guest = authenticate_google_user(
        db,
        google_subject="guest-subject",
        name="Guest",
        email="guest@example.com",
    )
    assert admin.role == UserRole.ADMIN
    assert guest.role == UserRole.GUEST

    with pytest.raises(HTTPException) as denied:
        require_spending_ledger_access(guest, db)
    assert denied.value.detail["code"] == "ACCOUNT_PENDING"

    member = update_user(db, guest.id, role=UserRole.MEMBER, actor_user_id=admin.id)
    with pytest.raises(HTTPException) as no_grant:
        require_spending_ledger_access(member, db)
    assert no_grant.value.detail["code"] == "APP_ACCESS_DISABLED"

    grant = authorization_service.set_application_grant(
        db,
        actor_user_id=admin.id,
        user_id=member.id,
        application="spending_ledger",
        enabled=True,
    )
    assert grant.enabled is True
    assert require_spending_ledger_access(member, db).id == member.id

    session_id, _, _ = session_service.create_session(db, member.id)
    assert db.get(type(grant), grant.id).enabled is True
    authorization_service.set_application_grant(
        db,
        actor_user_id=admin.id,
        user_id=member.id,
        application="spending_ledger",
        enabled=False,
    )
    assert db.get(RefreshSession, session_id).revoked_at is not None

    demoted = update_user(db, member.id, role=UserRole.GUEST, actor_user_id=admin.id)
    assert demoted.role == UserRole.GUEST


def test_last_enabled_admin_cannot_be_disabled_and_audit_is_queryable(db) -> None:
    admin = create_user(
        db, name="Admin", email="admin@example.com", role=UserRole.ADMIN
    )
    with pytest.raises(LastAdminError):
        update_user(
            db,
            admin.id,
            status=UserStatus.DISABLED,
            actor_user_id=admin.id,
        )

    category = ledger_service.create_category(
        db, admin.id, name="Audit", category_type=CategoryType.BOTH
    )
    ledger_service.create_record(
        db,
        admin.id,
        record_type=RecordType.INCOME,
        amount_minor=10,
        record_date=date(2026, 1, 1),
        category_id=category.id,
    )
    events = audit_service.list_events(db, target_user_id=admin.id)
    actions = {event.action for event in events}
    assert "ledger.category_updated" not in actions
    assert "ledger.record_created" in actions


def test_account_deletion_removes_owned_data_and_redacts_audit(
    db, tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(
        "app.features.spending_ledger.application.service.settings.upload_dir",
        str(tmp_path),
    )
    admin = create_user(
        db, name="Admin", email="admin@example.com", role=UserRole.ADMIN
    )
    member = create_user(db, name="Member", email="member@example.com")
    category = ledger_service.create_category(db, member.id, name="Receipts")
    record = ledger_service.create_record(
        db,
        member.id,
        record_type=RecordType.EXPENSE,
        amount_minor=100,
        record_date=date(2026, 1, 1),
        category_id=category.id,
    )
    attachment = ledger_service.create_attachment(
        db,
        member.id,
        record.id,
        content=b"\x89PNG\r\n\x1a\nimage",
        content_type="image/png",
    )
    attachment_path = ledger_service.attachment_file_path(attachment)

    ensure_user_deletable(db, member.id)
    ledger_service.delete_owner_data(db, member.id)
    delete_user(db, member.id, actor_user_id=admin.id)

    assert db.get(User, member.id) is None
    assert (
        db.query(LedgerRecord).filter(LedgerRecord.owner_id == member.id).count() == 0
    )
    assert db.query(Attachment).filter(Attachment.owner_id == member.id).count() == 0
    assert not attachment_path.exists()
    events = db.query(AuditEvent).filter(AuditEvent.entity_id == str(record.id)).all()
    assert events
    assert all(event.target_user_id is None for event in events)
