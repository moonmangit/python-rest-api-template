from fastapi import APIRouter, HTTPException, status

from app.features.auth.presentation.dependencies import AdminUser
from app.features.user.application import service as user_service
from app.features.user.domain.model import User
from app.features.user.presentation.schemas import UserCreate, UserResponse, UserUpdate
from app.shared.dependencies import SessionDep

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/", response_model=list[UserResponse])
def list_users(_: AdminUser, db: SessionDep) -> list[User]:
    return user_service.list_users(db)


@router.post(
    "/",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_user(user: UserCreate, _: AdminUser, db: SessionDep) -> User:
    try:
        return user_service.create_user(
            db,
            name=user.name,
            email=str(user.email),
            username=user.username,
            password=user.password,
            role=user.role,
        )
    except user_service.UserAlreadyExistsError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this username or email already exists",
        ) from None


@router.get("/{user_id}", response_model=UserResponse)
def get_user(user_id: int, _: AdminUser, db: SessionDep) -> User:
    try:
        return user_service.get_user(db, user_id)
    except user_service.UserNotFoundError:
        raise HTTPException(status_code=404, detail="User not found") from None


@router.patch("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int, changes: UserUpdate, _: AdminUser, db: SessionDep
) -> User:
    try:
        return user_service.update_user(
            db, user_id, changes.model_dump(exclude_unset=True)
        )
    except user_service.UserNotFoundError:
        raise HTTPException(status_code=404, detail="User not found") from None
    except user_service.UserAlreadyExistsError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this username or email already exists",
        ) from None
    except user_service.InvalidUserError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except user_service.LastAdminError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The last administrator cannot be demoted",
        ) from None


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: int, _: AdminUser, db: SessionDep) -> None:
    try:
        user_service.delete_user(db, user_id)
    except user_service.UserNotFoundError:
        raise HTTPException(status_code=404, detail="User not found") from None
    except user_service.LastAdminError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The last administrator cannot be deleted",
        ) from None
