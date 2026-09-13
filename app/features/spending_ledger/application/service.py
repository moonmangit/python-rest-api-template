import base64
import hashlib
import json
from calendar import monthrange
from datetime import date, datetime, timedelta
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.features.auth.application.audit_service import add_event
from app.features.spending_ledger.domain.model import (
    Attachment,
    Category,
    CategoryType,
    IdempotencyKey,
    LedgerRecord,
    RecordType,
)

_UNSET = object()


class LedgerNotFoundError(LookupError):
    pass


class LedgerValidationError(ValueError):
    pass


class LedgerConflictError(ValueError):
    pass


def create_category(
    db: Session,
    owner_id: int,
    *,
    name: str,
    parent_id: int | None = None,
    category_type: CategoryType = CategoryType.BOTH,
    sort_order: int = 0,
) -> Category:
    category_type = CategoryType(category_type)
    name = _category_name(name)
    _validate_parent(db, owner_id, parent_id)
    _ensure_category_name_available(
        db, owner_id, parent_id, name, category_type=category_type
    )
    category = Category(
        owner_id=owner_id,
        parent_id=parent_id,
        name=name,
        category_type=category_type,
        sort_order=sort_order,
    )
    db.add(category)
    db.flush()
    add_event(
        db,
        action="ledger.category_created",
        entity_type="category",
        actor_user_id=owner_id,
        target_user_id=owner_id,
        entity_id=str(category.id),
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise LedgerConflictError("Category name already exists") from exc
    db.refresh(category)
    return category


def list_categories(db: Session, owner_id: int) -> list[Category]:
    return list(
        db.scalars(
            select(Category)
            .where(Category.owner_id == owner_id)
            .order_by(Category.parent_id, Category.sort_order, Category.id)
        ).all()
    )


def update_category(
    db: Session,
    owner_id: int,
    category_id: int,
    *,
    name: str | None = None,
    sort_order: int | None = None,
    category_type: CategoryType | None = None,
) -> Category:
    category = _get_category(db, owner_id, category_id)
    if category_type is not None:
        category_type = CategoryType(category_type)
    if name is not None:
        normalized_name = _category_name(name)
        _ensure_category_name_available(
            db,
            owner_id,
            category.parent_id,
            normalized_name,
            category.id,
            category_type or category.category_type,
        )
        category.name = normalized_name
    elif category_type is not None and category_type != category.category_type:
        _ensure_category_name_available(
            db,
            owner_id,
            category.parent_id,
            category.name,
            category.id,
            category_type,
        )
    if sort_order is not None:
        category.sort_order = sort_order
    if category_type is not None:
        category.category_type = category_type
    add_event(
        db,
        action="ledger.category_updated",
        entity_type="category",
        actor_user_id=owner_id,
        target_user_id=owner_id,
        entity_id=str(category.id),
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise LedgerConflictError("Category name already exists") from exc
    db.refresh(category)
    return category


def set_category_archived(
    db: Session, owner_id: int, category_id: int, archived: bool
) -> Category:
    category = _get_category(db, owner_id, category_id)
    ids = [category.id]
    while ids:
        descendants = db.scalars(
            select(Category.id).where(
                Category.owner_id == owner_id, Category.parent_id.in_(ids)
            )
        ).all()
        ids = list(descendants)
        if ids:
            db.query(Category).filter(Category.id.in_(ids)).update(
                {Category.archived: archived}, synchronize_session="fetch"
            )
    category.archived = archived
    add_event(
        db,
        action="ledger.category_archived" if archived else "ledger.category_restored",
        entity_type="category",
        actor_user_id=owner_id,
        target_user_id=owner_id,
        entity_id=str(category.id),
    )
    db.commit()
    db.refresh(category)
    return category


def create_record(
    db: Session,
    owner_id: int,
    *,
    record_type: RecordType,
    amount_minor: int,
    record_date: date,
    category_id: int,
    subcategory_id: int | None = None,
    note: str | None = None,
    currency_code: str = "USD",
    idempotency_key: str | None = None,
) -> LedgerRecord:
    record_type = RecordType(record_type)
    if not isinstance(record_date, date):
        raise LedgerValidationError("Record date is invalid")
    payload = {
        "record_type": record_type.value,
        "amount_minor": amount_minor,
        "record_date": record_date.isoformat(),
        "category_id": category_id,
        "subcategory_id": subcategory_id,
        "note": note,
        "currency_code": currency_code,
    }
    request_hash = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if idempotency_key:
        previous = db.scalar(
            select(IdempotencyKey).where(
                IdempotencyKey.owner_id == owner_id,
                IdempotencyKey.key == idempotency_key,
            )
        )
        if previous is not None:
            if previous.request_hash != request_hash:
                raise LedgerConflictError(
                    "Idempotency key was used for another request"
                )
            return _get_record(db, owner_id, previous.record_id)

    _validate_record(
        db,
        owner_id,
        record_type,
        amount_minor,
        record_date,
        category_id,
        subcategory_id,
        note,
        currency_code,
    )
    record = LedgerRecord(
        owner_id=owner_id,
        record_type=record_type,
        amount_minor=amount_minor,
        currency_code=currency_code,
        record_date=record_date,
        category_id=category_id,
        subcategory_id=subcategory_id,
        note=note.strip() if note else None,
    )
    db.add(record)
    db.flush()
    if idempotency_key:
        db.add(
            IdempotencyKey(
                owner_id=owner_id,
                key=idempotency_key,
                request_hash=request_hash,
                record_id=record.id,
            )
        )
    add_event(
        db,
        action="ledger.record_created",
        entity_type="record",
        actor_user_id=owner_id,
        target_user_id=owner_id,
        entity_id=str(record.id),
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if idempotency_key:
            previous = db.scalar(
                select(IdempotencyKey).where(
                    IdempotencyKey.owner_id == owner_id,
                    IdempotencyKey.key == idempotency_key,
                )
            )
            if previous is not None and previous.request_hash == request_hash:
                return _get_record(db, owner_id, previous.record_id)
        raise LedgerConflictError("Record conflicts with existing data") from exc
    db.refresh(record)
    return record


def list_records(
    db: Session,
    owner_id: int,
    *,
    category_id: int | None = None,
    subcategory_id: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    record_type: RecordType | None = None,
    currency_code: str = "USD",
    cursor: str | None = None,
    limit: int = 50,
) -> tuple[list[LedgerRecord], str | None]:
    if not 1 <= limit <= 100:
        raise LedgerValidationError("Limit must be between 1 and 100")
    _validate_currency(currency_code)
    query = select(LedgerRecord).where(
        LedgerRecord.owner_id == owner_id,
        LedgerRecord.currency_code == currency_code,
    )
    query = _record_filters(
        db,
        query,
        owner_id,
        category_id,
        subcategory_id,
        start_date,
        end_date,
        record_type,
    )
    if cursor:
        cursor_date, cursor_id = _decode_cursor(cursor)
        query = query.where(
            or_(
                LedgerRecord.record_date < cursor_date,
                and_(
                    LedgerRecord.record_date == cursor_date,
                    LedgerRecord.id < cursor_id,
                ),
            )
        )
    records = list(
        db.scalars(
            query.order_by(
                LedgerRecord.record_date.desc(), LedgerRecord.id.desc()
            ).limit(limit + 1)
        ).all()
    )
    next_cursor = None
    if len(records) > limit:
        records.pop()
        last = records[-1]
        next_cursor = _encode_cursor(last.record_date, last.id)
    return records, next_cursor


def update_record(
    db: Session,
    owner_id: int,
    record_id: int,
    *,
    record_type: RecordType | None = None,
    amount_minor: int | None = None,
    record_date: date | None = None,
    category_id: int | None = None,
    subcategory_id: int | None | object = _UNSET,
    note: str | None | object = _UNSET,
    currency_code: str | None = None,
) -> LedgerRecord:
    record = _get_record(db, owner_id, record_id)
    new_type = (
        RecordType(record_type) if record_type is not None else record.record_type
    )
    new_amount = amount_minor if amount_minor is not None else record.amount_minor
    new_category = category_id if category_id is not None else record.category_id
    new_subcategory = (
        record.subcategory_id if subcategory_id is _UNSET else subcategory_id
    )
    new_currency = currency_code or record.currency_code
    _validate_record(
        db,
        owner_id,
        new_type,
        new_amount,
        record_date or record.record_date,
        new_category,
        new_subcategory,
        record.note if note is _UNSET else note,
        new_currency,
    )
    record.record_type = new_type
    record.amount_minor = new_amount
    record.record_date = record_date or record.record_date
    record.category_id = new_category
    record.subcategory_id = new_subcategory
    record.note = record.note if note is _UNSET else (note.strip() if note else None)
    record.currency_code = new_currency
    add_event(
        db,
        action="ledger.record_updated",
        entity_type="record",
        actor_user_id=owner_id,
        target_user_id=owner_id,
        entity_id=str(record.id),
    )
    db.commit()
    db.refresh(record)
    return record


def delete_record(db: Session, owner_id: int, record_id: int) -> list[str]:
    record = _get_record(db, owner_id, record_id)
    record_values = {
        "id": record.id,
        "owner_id": record.owner_id,
        "record_type": record.record_type,
        "amount_minor": record.amount_minor,
        "currency_code": record.currency_code,
        "record_date": record.record_date,
        "category_id": record.category_id,
        "subcategory_id": record.subcategory_id,
        "note": record.note,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
    }
    attachment_values = [
        {
            "id": attachment.id,
            "owner_id": attachment.owner_id,
            "record_id": attachment.record_id,
            "storage_key": attachment.storage_key,
            "content_type": attachment.content_type,
            "byte_size": attachment.byte_size,
            "checksum": attachment.checksum,
            "created_at": attachment.created_at,
        }
        for attachment in db.scalars(
            select(Attachment).where(Attachment.record_id == record.id)
        ).all()
    ]
    idempotency_values = [
        {
            "id": key.id,
            "owner_id": key.owner_id,
            "key": key.key,
            "request_hash": key.request_hash,
            "record_id": key.record_id,
            "created_at": key.created_at,
        }
        for key in db.scalars(
            select(IdempotencyKey).where(IdempotencyKey.record_id == record.id)
        ).all()
    ]
    keys = list(
        db.scalars(
            select(Attachment.storage_key).where(Attachment.record_id == record.id)
        ).all()
    )
    db.query(Attachment).filter(Attachment.record_id == record.id).delete(
        synchronize_session=False
    )
    db.query(IdempotencyKey).filter(IdempotencyKey.record_id == record.id).delete(
        synchronize_session=False
    )
    add_event(
        db,
        action="ledger.record_deleted",
        entity_type="record",
        actor_user_id=owner_id,
        target_user_id=owner_id,
        entity_id=str(record.id),
    )
    db.delete(record)
    committed = False
    try:
        db.commit()
        committed = True
        _remove_files(keys)
    except Exception:
        db.rollback()
        if committed:
            db.expunge_all()
            if db.get(LedgerRecord, record_id) is None:
                db.add(LedgerRecord(**record_values))
                db.flush()
                db.add_all(Attachment(**values) for values in attachment_values)
                db.add_all(IdempotencyKey(**values) for values in idempotency_values)
            db.commit()
        raise
    return keys


def delete_owner_data(
    db: Session, owner_id: int, *, actor_user_id: int | None = None
) -> list[str]:
    keys = list(
        db.scalars(
            select(Attachment.storage_key).where(Attachment.owner_id == owner_id)
        ).all()
    )
    record_ids = db.scalars(
        select(LedgerRecord.id).where(LedgerRecord.owner_id == owner_id)
    ).all()
    for record_id in record_ids:
        add_event(
            db,
            action="ledger.record_deleted",
            entity_type="record",
            actor_user_id=actor_user_id,
            target_user_id=owner_id,
            entity_id=str(record_id),
        )
    db.query(Attachment).filter(Attachment.owner_id == owner_id).delete(
        synchronize_session=False
    )
    db.query(IdempotencyKey).filter(IdempotencyKey.owner_id == owner_id).delete(
        synchronize_session=False
    )
    db.query(LedgerRecord).filter(LedgerRecord.owner_id == owner_id).delete(
        synchronize_session=False
    )
    db.query(Category).filter(Category.owner_id == owner_id).delete(
        synchronize_session=False
    )
    db.commit()
    _remove_files(keys)
    return keys


def report(
    db: Session,
    owner_id: int,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
    category_id: int | None = None,
    subcategory_id: int | None = None,
    record_type: RecordType | None = None,
    currency_code: str = "USD",
    granularity: str = "month",
    timezone_name: str = "UTC",
) -> dict:
    start_date, end_date = _report_range(start_date, end_date, timezone_name)
    if end_date < start_date:
        raise LedgerValidationError("End date must not precede start date")
    months = (
        (end_date.year - start_date.year) * 12 + end_date.month - start_date.month + 1
    )
    if months > 12:
        raise LedgerValidationError("Report range cannot exceed 12 months")
    _validate_currency(currency_code)
    if granularity not in {"day", "month"}:
        raise LedgerValidationError("Granularity must be day or month")
    query = select(LedgerRecord).where(
        LedgerRecord.owner_id == owner_id,
        LedgerRecord.currency_code == currency_code,
    )
    records = list(
        db.scalars(
            _record_filters(
                db,
                query,
                owner_id,
                category_id,
                subcategory_id,
                start_date,
                end_date,
                record_type,
            )
        ).all()
    )
    income = sum(r.amount_minor for r in records if r.record_type == RecordType.INCOME)
    expense = sum(
        r.amount_minor for r in records if r.record_type == RecordType.EXPENSE
    )
    categories = {
        category.id: category.name
        for category in db.scalars(
            select(Category).where(Category.owner_id == owner_id)
        )
    }
    breakdown: dict[str, dict[str, int]] = {}
    for record in records:
        category = categories.get(record.category_id, "Unknown")
        subcategory = categories.get(record.subcategory_id, "")
        key = f"{category}/{subcategory}" if subcategory else category
        bucket = breakdown.setdefault(key, {"income": 0, "expense": 0})
        bucket[record.record_type.value] += record.amount_minor
    series = _time_series(records, start_date, end_date, granularity)
    return {
        "currency_code": currency_code,
        "start_date": start_date,
        "end_date": end_date,
        "income_total": income,
        "expense_total": expense,
        "net_total": income - expense,
        "record_count": len(records),
        "breakdown": breakdown,
        "time_series": series,
    }


def create_attachment(
    db: Session,
    owner_id: int,
    record_id: int,
    *,
    content: bytes,
    content_type: str,
) -> Attachment:
    record = _get_record(db, owner_id, record_id)
    current_count = (
        db.query(Attachment).filter(Attachment.record_id == record.id).count()
    )
    if current_count >= 3:
        raise LedgerValidationError("A record cannot have more than 3 attachments")
    _validate_image(content, content_type)
    extension = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}[
        content_type
    ]
    key = f"{uuid4().hex}.{extension}"
    path = _storage_path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    committed = False
    try:
        path.write_bytes(content)
        attachment = Attachment(
            owner_id=owner_id,
            record_id=record.id,
            storage_key=key,
            content_type=content_type,
            byte_size=len(content),
            checksum=hashlib.sha256(content).hexdigest(),
        )
        db.add(attachment)
        db.flush()
        add_event(
            db,
            action="ledger.attachment_created",
            entity_type="attachment",
            actor_user_id=owner_id,
            target_user_id=owner_id,
            entity_id=str(attachment.id),
        )
        db.commit()
        committed = True
    except Exception:
        db.rollback()
        if not committed:
            path.unlink(missing_ok=True)
        raise
    db.refresh(attachment)
    return attachment


def replace_attachment(
    db: Session,
    owner_id: int,
    attachment_id: int,
    *,
    content: bytes,
    content_type: str,
) -> Attachment:
    attachment = get_attachment(db, owner_id, attachment_id)
    _validate_image(content, content_type)
    extension = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}[
        content_type
    ]
    new_key = f"{uuid4().hex}.{extension}"
    new_path = _storage_path(new_key)
    old_key = attachment.storage_key
    old_values = {
        "storage_key": old_key,
        "content_type": attachment.content_type,
        "byte_size": attachment.byte_size,
        "checksum": attachment.checksum,
    }
    new_path.parent.mkdir(parents=True, exist_ok=True)
    committed = False
    try:
        new_path.write_bytes(content)
        attachment.storage_key = new_key
        attachment.content_type = content_type
        attachment.byte_size = len(content)
        attachment.checksum = hashlib.sha256(content).hexdigest()
        add_event(
            db,
            action="ledger.attachment_updated",
            entity_type="attachment",
            actor_user_id=owner_id,
            target_user_id=owner_id,
            entity_id=str(attachment.id),
        )
        db.commit()
        committed = True
        _remove_files([old_key])
    except Exception:
        if not committed:
            db.rollback()
            new_path.unlink(missing_ok=True)
        else:
            attachment = db.get(Attachment, attachment_id)
            if attachment is not None:
                for field, value in old_values.items():
                    setattr(attachment, field, value)
                db.commit()
            new_path.unlink(missing_ok=True)
        raise
    db.refresh(attachment)
    return attachment


def get_attachment(db: Session, owner_id: int, attachment_id: int) -> Attachment:
    attachment = db.scalar(
        select(Attachment).where(
            Attachment.id == attachment_id, Attachment.owner_id == owner_id
        )
    )
    if attachment is None:
        raise LedgerNotFoundError("Attachment not found")
    return attachment


def list_attachments(db: Session, owner_id: int, record_id: int) -> list[Attachment]:
    _get_record(db, owner_id, record_id)
    return list(
        db.scalars(
            select(Attachment)
            .where(Attachment.owner_id == owner_id, Attachment.record_id == record_id)
            .order_by(Attachment.id)
        ).all()
    )


def attachment_file_path(attachment: Attachment) -> Path:
    return _storage_path(attachment.storage_key)


def delete_attachment(db: Session, owner_id: int, attachment_id: int) -> str:
    attachment = get_attachment(db, owner_id, attachment_id)
    key = attachment.storage_key
    values = {
        "id": attachment.id,
        "owner_id": attachment.owner_id,
        "record_id": attachment.record_id,
        "storage_key": attachment.storage_key,
        "content_type": attachment.content_type,
        "byte_size": attachment.byte_size,
        "checksum": attachment.checksum,
        "created_at": attachment.created_at,
    }
    add_event(
        db,
        action="ledger.attachment_deleted",
        entity_type="attachment",
        actor_user_id=owner_id,
        target_user_id=owner_id,
        entity_id=str(attachment.id),
    )
    db.delete(attachment)
    committed = False
    try:
        db.commit()
        committed = True
        _remove_files([key])
    except Exception:
        db.rollback()
        if committed and db.get(Attachment, attachment_id) is None:
            db.add(Attachment(**values))
            db.commit()
        raise
    return key


def _get_category(db: Session, owner_id: int, category_id: int) -> Category:
    category = db.scalar(
        select(Category).where(
            Category.id == category_id, Category.owner_id == owner_id
        )
    )
    if category is None:
        raise LedgerNotFoundError("Category not found")
    return category


def _get_record(db: Session, owner_id: int, record_id: int) -> LedgerRecord:
    record = db.scalar(
        select(LedgerRecord).where(
            LedgerRecord.id == record_id, LedgerRecord.owner_id == owner_id
        )
    )
    if record is None:
        raise LedgerNotFoundError("Record not found")
    return record


def get_record(db: Session, owner_id: int, record_id: int) -> LedgerRecord:
    return _get_record(db, owner_id, record_id)


def _category_name(name: str) -> str:
    name = name.strip()
    if not name or len(name) > 100:
        raise LedgerValidationError("Category name must contain 1 to 100 characters")
    return name


def _validate_parent(db: Session, owner_id: int, parent_id: int | None) -> None:
    if parent_id is None:
        return
    parent = _get_category(db, owner_id, parent_id)
    if parent.parent_id is not None:
        raise LedgerValidationError("Only one subcategory level is supported")
    if parent.archived:
        raise LedgerValidationError("Archived categories cannot have new children")


def _ensure_category_name_available(
    db: Session,
    owner_id: int,
    parent_id: int | None,
    name: str,
    category_id: int | None = None,
    category_type: CategoryType = CategoryType.BOTH,
) -> None:
    query = select(Category.id).where(
        Category.owner_id == owner_id,
        Category.name == name,
        Category.category_type == category_type,
    )
    query = query.where(
        Category.parent_id.is_(None)
        if parent_id is None
        else Category.parent_id == parent_id
    )
    if category_id is not None:
        query = query.where(Category.id != category_id)
    if db.scalar(query) is not None:
        raise LedgerConflictError("Category name already exists")


def _validate_record(
    db: Session,
    owner_id: int,
    record_type: RecordType,
    amount_minor: int,
    record_date: date,
    category_id: int,
    subcategory_id: int | None,
    note: str | None,
    currency_code: str,
) -> None:
    if amount_minor <= 0:
        raise LedgerValidationError("Amount must be greater than zero")
    if not isinstance(record_date, date):
        raise LedgerValidationError("Record date is invalid")
    _validate_currency(currency_code)
    if note is not None and len(note) > 5000:
        raise LedgerValidationError("Note cannot exceed 5,000 characters")
    category = _get_category(db, owner_id, category_id)
    if (
        category.parent_id is not None
        or category.archived
        or not _category_allows(category.category_type, record_type)
    ):
        raise LedgerValidationError("Category cannot be used for this record")
    if subcategory_id is not None:
        subcategory = _get_category(db, owner_id, subcategory_id)
        if (
            subcategory.parent_id != category.id
            or subcategory.archived
            or not _category_allows(subcategory.category_type, record_type)
        ):
            raise LedgerValidationError("Invalid subcategory")


def _category_allows(category_type: CategoryType, record_type: RecordType) -> bool:
    return category_type in (CategoryType.BOTH, CategoryType(record_type.value))


def _validate_currency(currency_code: str) -> None:
    if currency_code != "USD":
        raise LedgerValidationError("Only USD is supported")


def _record_filters(
    db: Session,
    query,
    owner_id: int,
    category_id: int | None,
    subcategory_id: int | None,
    start_date: date | None,
    end_date: date | None,
    record_type: RecordType | None,
):
    if category_id is not None:
        descendants = db.scalars(
            select(Category.id).where(
                Category.owner_id == owner_id, Category.parent_id == category_id
            )
        ).all()
        query = query.where(
            LedgerRecord.category_id == category_id
            if not descendants
            else or_(
                LedgerRecord.category_id == category_id,
                LedgerRecord.subcategory_id.in_(descendants),
            )
        )
    if subcategory_id is not None:
        query = query.where(LedgerRecord.subcategory_id == subcategory_id)
    if start_date is not None:
        query = query.where(LedgerRecord.record_date >= start_date)
    if end_date is not None:
        query = query.where(LedgerRecord.record_date <= end_date)
    if record_type is not None:
        query = query.where(LedgerRecord.record_type == record_type)
    return query


def _report_range(
    start_date: date | None, end_date: date | None, timezone_name: str
) -> tuple[date, date]:
    if start_date is not None or end_date is not None:
        return start_date or end_date, end_date or start_date
    try:
        today = datetime.now(ZoneInfo(timezone_name)).date()
    except ZoneInfoNotFoundError as exc:
        raise LedgerValidationError("Invalid timezone") from exc
    return today.replace(day=1), today.replace(
        day=monthrange(today.year, today.month)[1]
    )


def _time_series(
    records: list[LedgerRecord], start_date: date, end_date: date, granularity: str
) -> list[dict]:
    totals: dict[str, dict[str, int]] = {}
    cursor = start_date
    while cursor <= end_date:
        key = cursor.isoformat() if granularity == "day" else cursor.strftime("%Y-%m")
        totals.setdefault(key, {"income": 0, "expense": 0})
        if granularity == "day":
            cursor += timedelta(days=1)
        else:
            cursor = (cursor.replace(day=28) + timedelta(days=4)).replace(day=1)
    for record in records:
        key = (
            record.record_date.isoformat()
            if granularity == "day"
            else record.record_date.strftime("%Y-%m")
        )
        totals[key][record.record_type.value] += record.amount_minor
    return [
        {
            "period": key,
            "income": values["income"],
            "expense": values["expense"],
            "net": values["income"] - values["expense"],
        }
        for key, values in totals.items()
    ]


def _encode_cursor(record_date: date, record_id: int) -> str:
    raw = f"{record_date.isoformat()}:{record_id}".encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _decode_cursor(cursor: str) -> tuple[date, int]:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        raw_date, raw_id = base64.urlsafe_b64decode(padded).decode().split(":", 1)
        return date.fromisoformat(raw_date), int(raw_id)
    except (ValueError, UnicodeDecodeError) as exc:
        raise LedgerValidationError("Invalid cursor") from exc


def _validate_image(content: bytes, content_type: str) -> None:
    if len(content) > 10 * 1024 * 1024:
        raise LedgerValidationError("Image cannot exceed 10 MB")
    signatures = {
        "image/jpeg": content.startswith(b"\xff\xd8\xff"),
        "image/png": content.startswith(b"\x89PNG\r\n\x1a\n"),
        "image/webp": content[:4] == b"RIFF" and content[8:12] == b"WEBP",
    }
    if not signatures.get(content_type, False):
        raise LedgerValidationError("Unsupported or invalid image")


def _storage_path(key: str) -> Path:
    root = Path(settings.upload_dir).resolve()
    path = (root / key).resolve()
    if root not in path.parents:
        raise LedgerValidationError("Invalid storage key")
    return path


def _remove_files(keys: list[str]) -> None:
    for key in keys:
        _storage_path(key).unlink(missing_ok=True)
