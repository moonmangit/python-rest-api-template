from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.features.spending_ledger.domain.model import CategoryType, RecordType


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    parent_id: int | None = None
    category_type: CategoryType = CategoryType.BOTH
    sort_order: int = 0


class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    category_type: CategoryType | None = None
    sort_order: int | None = None


class CategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_id: int
    parent_id: int | None
    name: str
    category_type: CategoryType
    sort_order: int
    archived: bool
    created_at: datetime
    updated_at: datetime


class RecordCreate(BaseModel):
    record_type: RecordType
    amount_minor: int = Field(gt=0)
    record_date: date
    category_id: int
    subcategory_id: int | None = None
    note: str | None = Field(default=None, max_length=5000)
    currency_code: str = Field(default="USD", min_length=3, max_length=3)


class RecordUpdate(BaseModel):
    record_type: RecordType | None = None
    amount_minor: int | None = Field(default=None, gt=0)
    record_date: date | None = None
    category_id: int | None = None
    subcategory_id: int | None = None
    note: str | None = Field(default=None, max_length=5000)
    currency_code: str | None = Field(default=None, min_length=3, max_length=3)


class RecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_id: int
    record_type: RecordType
    amount_minor: int
    currency_code: str
    record_date: date
    category_id: int
    subcategory_id: int | None
    note: str | None
    created_at: datetime
    updated_at: datetime


class RecordPage(BaseModel):
    items: list[RecordResponse]
    next_cursor: str | None


class AttachmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_id: int
    record_id: int
    content_type: str
    byte_size: int
    checksum: str
    created_at: datetime


class TimeSeriesPoint(BaseModel):
    period: str
    income: int
    expense: int
    net: int


class ReportResponse(BaseModel):
    currency_code: str
    start_date: date
    end_date: date
    income_total: int
    expense_total: int
    net_total: int
    record_count: int
    breakdown: dict[str, dict[str, int]]
    time_series: list[TimeSeriesPoint]
