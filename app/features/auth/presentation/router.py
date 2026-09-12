from authlib.integrations.base_client.errors import OAuthError
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import RedirectResponse, Response

from app.core.config import settings
from app.core.security import clear_auth_cookie, create_access_token, set_auth_cookie
from app.features.auth.application import service as auth_service
from app.features.users.application import service as user_service
from app.features.users.domain.model import User
from app.features.users.presentation.schemas import UserResponse
from app.shared.dependencies import CurrentUserDep, SessionDep

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/google/login")
async def google_login(request: Request) -> RedirectResponse:
    try:
        google = auth_service.get_google_client()
    except auth_service.GoogleOAuthNotConfiguredError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth is not configured",
        ) from None
    return await google.authorize_redirect(request, settings.google_redirect_uri)


@router.get("/google/callback", name="google_callback", response_class=RedirectResponse)
async def google_callback(request: Request, db: SessionDep) -> RedirectResponse:
    try:
        google = auth_service.get_google_client()
        token = await google.authorize_access_token(request)
    except auth_service.GoogleOAuthNotConfiguredError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth is not configured",
        ) from None
    except OAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Google authentication failed: {exc.error}",
        ) from None

    userinfo = token.get("userinfo")
    if not userinfo or not userinfo.get("sub") or not userinfo.get("email"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google did not return a usable verified identity",
        )
    if not userinfo.get("email_verified"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Google email is not verified",
        )

    try:
        user = user_service.authenticate_google_user(
            db,
            google_subject=str(userinfo["sub"]),
            name=str(userinfo.get("name") or ""),
            email=str(userinfo["email"]),
        )
    except user_service.UserAlreadyExistsError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        ) from None
    except user_service.GoogleIdentityConflictError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This Google account or email is linked to another user",
        ) from None
    request.session.clear()
    response = RedirectResponse(
        url="/api/v1/auth/me", status_code=status.HTTP_303_SEE_OTHER
    )
    try:
        token = create_access_token(user.id)
    except RuntimeError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="JWT authentication is not configured",
        ) from None
    set_auth_cookie(response, token)
    return response


@router.get("/me", response_model=UserResponse)
def me(user: CurrentUserDep) -> User:
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request) -> Response:
    request.session.clear()
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_auth_cookie(response)
    return response
