from fastapi import APIRouter, HTTPException, Response, status

from app.core.config import settings
from app.core.security import create_access_token
from app.features.auth.application import service as auth_service
from app.features.auth.presentation.dependencies import CurrentUser
from app.features.user.application import service as user_service
from app.features.user.domain.model import User
from app.features.user.presentation.schemas import (
    LoginRequest,
    UserRegistration,
    UserResponse,
)
from app.shared.dependencies import SessionDep

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=token,
        max_age=settings.jwt_expire_minutes * 60,
        httponly=True,
        secure=settings.environment == "production",
        samesite="lax",
        path="/",
    )


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(user: UserRegistration, db: SessionDep) -> User:
    try:
        return user_service.create_user(
            db,
            name=user.name,
            email=str(user.email),
            username=user.username,
            password=user.password,
        )
    except user_service.UserAlreadyExistsError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this username or email already exists",
        ) from None


@router.post("/login", response_model=UserResponse)
def login(user: LoginRequest, response: Response, db: SessionDep) -> User:
    authenticated_user = auth_service.authenticate_user(
        db, username=user.username, password=user.password
    )
    if authenticated_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    _set_auth_cookie(response, create_access_token(authenticated_user.id))
    return authenticated_user


@router.get("/me", response_model=UserResponse)
def current_user(user: CurrentUser) -> User:
    return user


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(response: Response, user: CurrentUser, db: SessionDep) -> None:
    try:
        user_service.delete_user(db, user.id)
    except user_service.LastAdminError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The last administrator cannot delete their account",
        ) from None
    response.delete_cookie(settings.auth_cookie_name, path="/")


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response) -> None:
    response.delete_cookie(settings.auth_cookie_name, path="/")
