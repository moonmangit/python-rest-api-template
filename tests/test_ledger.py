from datetime import date

import pytest

from app.core.config import settings
from app.features.spending_ledger.application import service
from app.features.spending_ledger.domain import CategoryType, RecordType
from app.features.users.application.service import create_user
from app.features.users.domain import UserRole


def _admin(db):
    return create_user(db, name="Admin", email="admin@example.com", role=UserRole.ADMIN)


def test_records_are_idempotent_and_reports_include_zero_buckets(db) -> None:
    user = _admin(db)
    category = service.create_category(
        db, user.id, name="Household", category_type=CategoryType.BOTH
    )
    subcategory = service.create_category(
        db,
        user.id,
        name="Food",
        parent_id=category.id,
        category_type=CategoryType.EXPENSE,
    )
    expense = service.create_record(
        db,
        user.id,
        record_type=RecordType.EXPENSE,
        amount_minor=1000,
        record_date=date(2026, 1, 2),
        category_id=category.id,
        subcategory_id=subcategory.id,
        idempotency_key="expense-1",
    )
    retry = service.create_record(
        db,
        user.id,
        record_type=RecordType.EXPENSE,
        amount_minor=1000,
        record_date=date(2026, 1, 2),
        category_id=category.id,
        subcategory_id=subcategory.id,
        idempotency_key="expense-1",
    )

    assert retry.id == expense.id
    result = service.report(
        db,
        user.id,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 3, 31),
        category_id=category.id,
        granularity="month",
    )
    assert result["expense_total"] == 1000
    assert result["income_total"] == 0
    assert result["net_total"] == -1000
    assert [point["period"] for point in result["time_series"]] == [
        "2026-01",
        "2026-02",
        "2026-03",
    ]
    assert result["time_series"][1]["expense"] == 0


def test_category_lifecycle_type_scope_and_record_update(db) -> None:
    user = _admin(db)
    expense = service.create_category(
        db, user.id, name="Utilities", category_type=CategoryType.EXPENSE
    )
    income = service.create_category(
        db, user.id, name="Utilities", category_type=CategoryType.INCOME
    )
    with pytest.raises(service.LedgerConflictError):
        service.create_category(
            db, user.id, name="Utilities", category_type=CategoryType.EXPENSE
        )
    child = service.create_category(
        db,
        user.id,
        name="Power",
        parent_id=expense.id,
        category_type=CategoryType.EXPENSE,
    )
    record = service.create_record(
        db,
        user.id,
        record_type=RecordType.EXPENSE,
        amount_minor=20,
        record_date=date(2026, 2, 1),
        category_id=expense.id,
        subcategory_id=child.id,
        note="before",
    )
    service.update_record(db, user.id, record.id, amount_minor=30)
    assert service.get_record(db, user.id, record.id).note == "before"
    service.set_category_archived(db, user.id, expense.id, True)
    assert (
        next(
            category
            for category in service.list_categories(db, user.id)
            if category.id == child.id
        ).archived
        is True
    )
    assert service.get_record(db, user.id, record.id).id == record.id
    service.set_category_archived(db, user.id, expense.id, False)
    assert (
        next(
            category
            for category in service.list_categories(db, user.id)
            if category.id == child.id
        ).archived
        is False
    )
    assert income.category_type == CategoryType.INCOME


def test_archived_category_cannot_be_used_and_owner_isolation_is_enforced(db) -> None:
    owner = _admin(db)
    other = create_user(db, name="Other", email="other@example.com")
    category = service.create_category(
        db, owner.id, name="Travel", category_type=CategoryType.EXPENSE
    )
    service.create_record(
        db,
        owner.id,
        record_type=RecordType.EXPENSE,
        amount_minor=1,
        record_date=date.today(),
        category_id=category.id,
    )
    service.set_category_archived(db, owner.id, category.id, True)

    with pytest.raises(service.LedgerValidationError):
        service.create_record(
            db,
            owner.id,
            record_type=RecordType.EXPENSE,
            amount_minor=1,
            record_date=date.today(),
            category_id=category.id,
        )
    records, next_cursor = service.list_records(db, other.id)
    assert records == []
    assert next_cursor is None


def test_record_filters_pagination_and_report_validation(db) -> None:
    user = _admin(db)
    expense = service.create_category(
        db, user.id, name="Expense", category_type=CategoryType.EXPENSE
    )
    income = service.create_category(
        db, user.id, name="Income", category_type=CategoryType.INCOME
    )
    service.create_record(
        db,
        user.id,
        record_type=RecordType.EXPENSE,
        amount_minor=200,
        record_date=date(2026, 3, 2),
        category_id=expense.id,
    )
    service.create_record(
        db,
        user.id,
        record_type=RecordType.INCOME,
        amount_minor=500,
        record_date=date(2026, 3, 1),
        category_id=income.id,
    )
    records, cursor = service.list_records(db, user.id, limit=1)
    assert len(records) == 1
    assert cursor is not None
    records, cursor = service.list_records(db, user.id, cursor=cursor, limit=1)
    assert len(records) == 1
    assert cursor is None

    result = service.report(
        db,
        user.id,
        start_date=date(2026, 3, 1),
        end_date=date(2026, 3, 31),
        record_type=RecordType.INCOME,
        category_id=income.id,
        granularity="day",
    )
    assert result["income_total"] == 500
    assert result["expense_total"] == 0
    assert len(result["time_series"]) == 31
    with pytest.raises(service.LedgerValidationError):
        service.report(
            db,
            user.id,
            start_date=date(2026, 4, 1),
            end_date=date(2026, 3, 1),
        )
    with pytest.raises(service.LedgerValidationError):
        service.report(
            db,
            user.id,
            start_date=date(2020, 1, 1),
            end_date=date(2022, 1, 1),
        )
    with pytest.raises(service.LedgerValidationError):
        service.list_records(db, user.id, currency_code="EUR")


def test_attachment_is_stored_outside_database_and_deleted(
    db, tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    user = _admin(db)
    category = service.create_category(db, user.id, name="Receipts")
    record = service.create_record(
        db,
        user.id,
        record_type=RecordType.EXPENSE,
        amount_minor=500,
        record_date=date.today(),
        category_id=category.id,
    )
    attachment = service.create_attachment(
        db,
        user.id,
        record.id,
        content=b"\x89PNG\r\n\x1a\nimage",
        content_type="image/png",
    )
    path = service.attachment_file_path(attachment)
    assert path.is_file()
    assert service.get_attachment(db, user.id, attachment.id).byte_size == 13

    service.delete_attachment(db, user.id, attachment.id)
    assert not path.exists()


def test_attachment_validation_and_failed_commit_cleanup(
    db, tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    user = _admin(db)
    category = service.create_category(db, user.id, name="Receipts")
    record = service.create_record(
        db,
        user.id,
        record_type=RecordType.EXPENSE,
        amount_minor=500,
        record_date=date.today(),
        category_id=category.id,
    )
    with pytest.raises(service.LedgerValidationError):
        service.create_attachment(
            db,
            user.id,
            record.id,
            content=b"not-an-image",
            content_type="image/png",
        )
    with pytest.raises(service.LedgerValidationError):
        service.create_attachment(
            db,
            user.id,
            record.id,
            content=b"\xff\xd8\xff" + b"x" * (10 * 1024 * 1024),
            content_type="image/jpeg",
        )

    original_commit = db.commit
    db.commit = lambda: (_ for _ in ()).throw(RuntimeError("commit failed"))
    try:
        with pytest.raises(RuntimeError):
            service.create_attachment(
                db,
                user.id,
                record.id,
                content=b"\x89PNG\r\n\x1a\nimage",
                content_type="image/png",
            )
    finally:
        db.commit = original_commit
    assert list(tmp_path.iterdir()) == []
