from fastapi import APIRouter, HTTPException, status

from app.features.users.application import service as user_service
from app.features.users.domain.model import User
from app.features.users.presentation.schemas import UserCreate, UserResponse
from app.shared.dependencies import SessionDep

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/", response_model=list[UserResponse])
def list_users(db: SessionDep) -> list[User]:
    return user_service.list_users(db)


@router.post(
    "/",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_user(user: UserCreate, db: SessionDep) -> User:
    try:
        return user_service.create_user(
            db,
            name=user.name,
            email=str(user.email),
        )
    except user_service.UserAlreadyExistsError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        ) from None
