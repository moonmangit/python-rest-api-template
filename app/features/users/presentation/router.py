from fastapi import APIRouter, HTTPException, status

from app.features.users.application import service as user_service
from app.features.users.domain.model import User
from app.features.users.presentation.schemas import UserCreate, UserResponse, UserUpdate
from app.shared.dependencies import AdminUserDep, SessionDep

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/", response_model=list[UserResponse])
def list_users(_: AdminUserDep, db: SessionDep) -> list[User]:
    return user_service.list_users(db)


@router.post(
    "/",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_user(_: AdminUserDep, user: UserCreate, db: SessionDep) -> User:
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
    user_id: int, user: UserUpdate, _: AdminUserDep, db: SessionDep
) -> User:
    try:
        return user_service.update_user(
            db,
            user_id,
            name=user.name,
            email=str(user.email) if user.email is not None else None,
            role=user.role,
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
def delete_user(user_id: int, _: AdminUserDep, db: SessionDep) -> None:
    try:
        user_service.delete_user(db, user_id)
    except user_service.UserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        ) from None
    except user_service.LastAdminError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The final administrator cannot be deleted",
        ) from None
