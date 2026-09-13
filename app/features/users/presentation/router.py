from fastapi import APIRouter, HTTPException, Query, status

from app.features.auth.application import (
    audit_service,
    authorization_service,
    session_service,
)
from app.features.auth.presentation.schemas import (
    ApplicationGrantResponse,
    ApplicationGrantUpdate,
    AuditEventResponse,
)
from app.features.spending_ledger.application import service as ledger_service
from app.features.users.application import service as user_service
from app.features.users.domain.model import User
from app.features.users.presentation.schemas import UserCreate, UserResponse, UserUpdate
from app.shared.dependencies import AdminUserDep, CsrfDep, SessionDep

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/audit", response_model=list[AuditEventResponse])
def list_audit_events(
    _: AdminUserDep,
    db: SessionDep,
    target_user_id: int | None = None,
    limit: int = Query(default=100, ge=1, le=100),
):
    return audit_service.list_events(db, target_user_id=target_user_id, limit=limit)


@router.get("/", response_model=list[UserResponse])
def list_users(
    _: AdminUserDep,
    db: SessionDep,
    search: str | None = Query(default=None, max_length=255),
) -> list[User]:
    users = user_service.list_users(db)
    if search:
        search = search.lower()
        users = [
            user
            for user in users
            if search in user.email.lower() or search in user.name.lower()
        ]
    return users


@router.post(
    "/",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_user(_: AdminUserDep, user: UserCreate, db: SessionDep, __: CsrfDep) -> User:
    try:
        return user_service.create_user(
            db,
            name=user.name,
            email=str(user.email),
            role=user.role,
        )
    except user_service.UserAlreadyExistsError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        ) from None


@router.get("/{user_id}", response_model=UserResponse)
def get_user(user_id: int, _: AdminUserDep, db: SessionDep) -> User:
    try:
        return user_service.get_user(db, user_id)
    except user_service.UserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        ) from None


@router.patch("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int, user: UserUpdate, admin: AdminUserDep, db: SessionDep, __: CsrfDep
) -> User:
    try:
        return user_service.update_user(
            db,
            user_id,
            name=user.name,
            email=str(user.email) if user.email is not None else None,
            role=user.role,
            status=user.status,
            actor_user_id=admin.id,
        )
    except user_service.UserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        ) from None
    except user_service.UserAlreadyExistsError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        ) from None
    except user_service.InvalidUserError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from None
    except user_service.LastAdminError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The final administrator cannot be removed or demoted",
        ) from None


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: int, admin: AdminUserDep, db: SessionDep, __: CsrfDep) -> None:
    try:
        user_service.ensure_user_deletable(db, user_id)
        ledger_service.delete_owner_data(db, user_id)
        user_service.delete_user(db, user_id, actor_user_id=admin.id)
    except user_service.UserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        ) from None
    except user_service.LastAdminError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The final administrator cannot be deleted",
        ) from None


@router.patch(
    "/{user_id}/applications/{application}",
    response_model=ApplicationGrantResponse,
)
def update_application_grant(
    user_id: int,
    application: str,
    payload: ApplicationGrantUpdate,
    admin: AdminUserDep,
    db: SessionDep,
    _: CsrfDep,
):
    try:
        return authorization_service.set_application_grant(
            db,
            actor_user_id=admin.id,
            user_id=user_id,
            application=application,
            enabled=payload.enabled,
        )
    except user_service.UserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        ) from None


@router.post("/{user_id}/sessions/revoke", status_code=status.HTTP_204_NO_CONTENT)
def revoke_user_sessions(
    user_id: int, _: AdminUserDep, db: SessionDep, __: CsrfDep
) -> None:
    try:
        user_service.get_user(db, user_id)
    except user_service.UserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        ) from None
    session_service.revoke_all(db, user_id)
