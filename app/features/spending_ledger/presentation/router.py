from datetime import date

from fastapi import APIRouter, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import FileResponse, Response

from app.features.spending_ledger.application import service
from app.features.spending_ledger.domain.model import RecordType
from app.features.spending_ledger.presentation.schemas import (
    AttachmentResponse,
    CategoryCreate,
    CategoryResponse,
    CategoryUpdate,
    RecordCreate,
    RecordPage,
    RecordResponse,
    RecordUpdate,
    ReportResponse,
)
from app.shared.dependencies import CsrfDep, SessionDep, SpendingLedgerUserDep

router = APIRouter(prefix="/ledger", tags=["spending-ledger"])


@router.get("/categories", response_model=list[CategoryResponse])
def get_categories(user: SpendingLedgerUserDep, db: SessionDep):
    return service.list_categories(db, user.id)


@router.post(
    "/categories",
    response_model=CategoryResponse,
    status_code=status.HTTP_201_CREATED,
)
def post_category(
    payload: CategoryCreate,
    user: SpendingLedgerUserDep,
    db: SessionDep,
    _: CsrfDep,
):
    try:
        return service.create_category(db, user.id, **payload.model_dump())
    except service.LedgerNotFoundError as exc:
        raise _http_error(
            status.HTTP_404_NOT_FOUND, "CATEGORY_NOT_FOUND", str(exc)
        ) from None
    except service.LedgerConflictError as exc:
        raise _http_error(
            status.HTTP_409_CONFLICT, "CATEGORY_CONFLICT", str(exc)
        ) from None
    except service.LedgerValidationError as exc:
        raise _http_error(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "CATEGORY_INVALID", str(exc)
        ) from None


@router.patch("/categories/{category_id}", response_model=CategoryResponse)
def patch_category(
    category_id: int,
    payload: CategoryUpdate,
    user: SpendingLedgerUserDep,
    db: SessionDep,
    _: CsrfDep,
):
    try:
        return service.update_category(db, user.id, category_id, **payload.model_dump())
    except service.LedgerNotFoundError as exc:
        raise _http_error(
            status.HTTP_404_NOT_FOUND, "CATEGORY_NOT_FOUND", str(exc)
        ) from None
    except service.LedgerConflictError as exc:
        raise _http_error(
            status.HTTP_409_CONFLICT, "CATEGORY_CONFLICT", str(exc)
        ) from None
    except service.LedgerValidationError as exc:
        raise _http_error(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "CATEGORY_INVALID", str(exc)
        ) from None


@router.post("/categories/{category_id}/archive", response_model=CategoryResponse)
def archive_category(
    category_id: int,
    user: SpendingLedgerUserDep,
    db: SessionDep,
    _: CsrfDep,
):
    try:
        return service.set_category_archived(db, user.id, category_id, True)
    except service.LedgerNotFoundError as exc:
        raise _http_error(
            status.HTTP_404_NOT_FOUND, "CATEGORY_NOT_FOUND", str(exc)
        ) from None


@router.post("/categories/{category_id}/restore", response_model=CategoryResponse)
def restore_category(
    category_id: int,
    user: SpendingLedgerUserDep,
    db: SessionDep,
    _: CsrfDep,
):
    try:
        return service.set_category_archived(db, user.id, category_id, False)
    except service.LedgerNotFoundError as exc:
        raise _http_error(
            status.HTTP_404_NOT_FOUND, "CATEGORY_NOT_FOUND", str(exc)
        ) from None


@router.get("/records", response_model=RecordPage)
def get_records(
    user: SpendingLedgerUserDep,
    db: SessionDep,
    category_id: int | None = None,
    subcategory_id: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    record_type: RecordType | None = None,
    currency_code: str = Query(default="USD", min_length=3, max_length=3),
    cursor: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
):
    try:
        items, next_cursor = service.list_records(
            db,
            user.id,
            category_id=category_id,
            subcategory_id=subcategory_id,
            start_date=start_date,
            end_date=end_date,
            record_type=record_type,
            currency_code=currency_code,
            cursor=cursor,
            limit=limit,
        )
        return {"items": items, "next_cursor": next_cursor}
    except service.LedgerValidationError as exc:
        raise _http_error(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "INVALID_FILTER", str(exc)
        ) from None


@router.get("/records/{record_id}", response_model=RecordResponse)
def get_record(record_id: int, user: SpendingLedgerUserDep, db: SessionDep):
    try:
        return service.get_record(db, user.id, record_id)
    except service.LedgerNotFoundError as exc:
        raise _http_error(
            status.HTTP_404_NOT_FOUND, "RECORD_NOT_FOUND", str(exc)
        ) from None


@router.post(
    "/records", response_model=RecordResponse, status_code=status.HTTP_201_CREATED
)
def post_record(
    payload: RecordCreate,
    request: Request,
    user: SpendingLedgerUserDep,
    db: SessionDep,
    _: CsrfDep,
):
    try:
        return service.create_record(
            db,
            user.id,
            idempotency_key=request.headers.get("Idempotency-Key"),
            **payload.model_dump(),
        )
    except service.LedgerNotFoundError as exc:
        raise _http_error(
            status.HTTP_404_NOT_FOUND, "CATEGORY_NOT_FOUND", str(exc)
        ) from None
    except service.LedgerConflictError as exc:
        raise _http_error(
            status.HTTP_409_CONFLICT, "RECORD_CONFLICT", str(exc)
        ) from None
    except service.LedgerValidationError as exc:
        raise _http_error(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "RECORD_INVALID", str(exc)
        ) from None


@router.patch("/records/{record_id}", response_model=RecordResponse)
def patch_record(
    record_id: int,
    payload: RecordUpdate,
    user: SpendingLedgerUserDep,
    db: SessionDep,
    _: CsrfDep,
):
    try:
        return service.update_record(
            db, user.id, record_id, **payload.model_dump(exclude_unset=True)
        )
    except service.LedgerNotFoundError as exc:
        raise _http_error(
            status.HTTP_404_NOT_FOUND, "RECORD_NOT_FOUND", str(exc)
        ) from None
    except service.LedgerValidationError as exc:
        raise _http_error(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "RECORD_INVALID", str(exc)
        ) from None


@router.delete("/records/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_record(
    record_id: int,
    user: SpendingLedgerUserDep,
    db: SessionDep,
    _: CsrfDep,
) -> Response:
    try:
        service.delete_record(db, user.id, record_id)
    except service.LedgerNotFoundError as exc:
        raise _http_error(
            status.HTTP_404_NOT_FOUND, "RECORD_NOT_FOUND", str(exc)
        ) from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/records/{record_id}/attachments",
    response_model=AttachmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def post_attachment(
    record_id: int,
    file: UploadFile,
    user: SpendingLedgerUserDep,
    db: SessionDep,
    _: CsrfDep,
):
    content = await file.read(10 * 1024 * 1024 + 1)
    try:
        return service.create_attachment(
            db,
            user.id,
            record_id,
            content=content,
            content_type=file.content_type or "",
        )
    except service.LedgerNotFoundError as exc:
        raise _http_error(
            status.HTTP_404_NOT_FOUND, "RECORD_NOT_FOUND", str(exc)
        ) from None
    except service.LedgerValidationError as exc:
        raise _http_error(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "ATTACHMENT_INVALID", str(exc)
        ) from None


@router.get("/records/{record_id}/attachments", response_model=list[AttachmentResponse])
def get_attachments(record_id: int, user: SpendingLedgerUserDep, db: SessionDep):
    try:
        return service.list_attachments(db, user.id, record_id)
    except service.LedgerNotFoundError as exc:
        raise _http_error(
            status.HTTP_404_NOT_FOUND, "RECORD_NOT_FOUND", str(exc)
        ) from None


@router.get("/attachments/{attachment_id}")
def download_attachment(
    attachment_id: int, user: SpendingLedgerUserDep, db: SessionDep
):
    try:
        attachment = service.get_attachment(db, user.id, attachment_id)
        path = service.attachment_file_path(attachment)
    except service.LedgerNotFoundError as exc:
        raise _http_error(
            status.HTTP_404_NOT_FOUND, "ATTACHMENT_NOT_FOUND", str(exc)
        ) from None
    if not path.is_file():
        raise _http_error(
            status.HTTP_404_NOT_FOUND, "ATTACHMENT_NOT_FOUND", "Attachment not found"
        )
    return FileResponse(path, media_type=attachment.content_type)


@router.put("/attachments/{attachment_id}", response_model=AttachmentResponse)
async def replace_attachment(
    attachment_id: int,
    file: UploadFile,
    user: SpendingLedgerUserDep,
    db: SessionDep,
    _: CsrfDep,
):
    content = await file.read(10 * 1024 * 1024 + 1)
    try:
        return service.replace_attachment(
            db,
            user.id,
            attachment_id,
            content=content,
            content_type=file.content_type or "",
        )
    except service.LedgerNotFoundError as exc:
        raise _http_error(
            status.HTTP_404_NOT_FOUND, "ATTACHMENT_NOT_FOUND", str(exc)
        ) from None
    except service.LedgerValidationError as exc:
        raise _http_error(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "ATTACHMENT_INVALID", str(exc)
        ) from None


@router.delete("/attachments/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_attachment(
    attachment_id: int,
    user: SpendingLedgerUserDep,
    db: SessionDep,
    _: CsrfDep,
) -> Response:
    try:
        service.delete_attachment(db, user.id, attachment_id)
    except service.LedgerNotFoundError as exc:
        raise _http_error(
            status.HTTP_404_NOT_FOUND, "ATTACHMENT_NOT_FOUND", str(exc)
        ) from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/reports", response_model=ReportResponse)
def get_report(
    user: SpendingLedgerUserDep,
    db: SessionDep,
    start_date: date | None = None,
    end_date: date | None = None,
    category_id: int | None = None,
    subcategory_id: int | None = None,
    record_type: RecordType | None = None,
    currency_code: str = Query(default="USD", min_length=3, max_length=3),
    granularity: str = Query(default="month", pattern="^(day|month)$"),
):
    try:
        return service.report(
            db,
            user.id,
            start_date=start_date,
            end_date=end_date,
            category_id=category_id,
            subcategory_id=subcategory_id,
            record_type=record_type,
            currency_code=currency_code,
            granularity=granularity,
            timezone_name=user.timezone,
        )
    except service.LedgerValidationError as exc:
        raise _http_error(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "REPORT_INVALID", str(exc)
        ) from None


def _http_error(code: int, error_code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=code, detail={"code": error_code, "message": message}
    )
