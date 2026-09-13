from datetime import date, datetime, timezone
from enum import StrEnum

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class RecordType(StrEnum):
    INCOME = "income"
    EXPENSE = "expense"


class CategoryType(StrEnum):
    INCOME = "income"
    EXPENSE = "expense"
    BOTH = "both"


class Category(Base):
    __tablename__ = "ledger_categories"
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "parent_id",
            "name",
            "category_type",
            name="uq_ledger_categories_owner_parent_name_type",
        ),
        Index(
            "uq_ledger_categories_owner_parent_name_type_root",
            "owner_id",
            "parent_id",
            "name",
            "category_type",
            unique=True,
            postgresql_nulls_not_distinct=True,
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("ledger_categories.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    category_type: Mapped[CategoryType] = mapped_column(
        SqlEnum(
            CategoryType,
            native_enum=False,
            length=7,
            values_callable=lambda values: [value.value for value in values],
        ),
        nullable=False,
        default=CategoryType.BOTH,
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    archived: Mapped[bool] = mapped_column(nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class LedgerRecord(Base):
    __tablename__ = "ledger_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    record_type: Mapped[RecordType] = mapped_column(
        SqlEnum(
            RecordType,
            native_enum=False,
            length=7,
            values_callable=lambda values: [value.value for value in values],
        ),
        nullable=False,
    )
    amount_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False)
    record_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    category_id: Mapped[int] = mapped_column(
        ForeignKey("ledger_categories.id"), index=True, nullable=False
    )
    subcategory_id: Mapped[int | None] = mapped_column(
        ForeignKey("ledger_categories.id"), index=True, nullable=True
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class Attachment(Base):
    __tablename__ = "ledger_attachments"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    record_id: Mapped[int] = mapped_column(
        ForeignKey("ledger_records.id", ondelete="CASCADE"), index=True, nullable=False
    )
    storage_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class IdempotencyKey(Base):
    __tablename__ = "ledger_idempotency_keys"
    __table_args__ = (UniqueConstraint("owner_id", "key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    key: Mapped[str] = mapped_column(String(255), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    record_id: Mapped[int] = mapped_column(
        ForeignKey("ledger_records.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
