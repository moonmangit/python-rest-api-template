import base64
import hashlib
import secrets

from authlib.integrations.base_client.errors import OAuthError
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import RedirectResponse, Response

from app.core.config import settings
from app.core.security import (
    clear_auth_cookie,
    create_access_token,
    set_auth_cookie,
    set_csrf_cookie,
    set_refresh_cookie,
)
from app.features.auth.application import service as auth_service
from app.features.auth.application import session_service
from app.features.auth.application.audit_service import add_event
from app.features.spending_ledger.application import service as ledger_service
from app.features.users.application import service as user_service
from app.features.users.domain.model import User
from app.features.users.presentation.schemas import UserResponse
from app.shared.dependencies import CsrfDep, CurrentUserDep, SessionDep

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
    nonce = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest())
        .rstrip(b"=")
        .decode("ascii")
    )
    request.session["oauth_nonce"] = nonce
    request.session["oauth_code_verifier"] = verifier
    return await google.authorize_redirect(
        request,
        settings.google_redirect_uri,
        nonce=nonce,
        code_challenge=challenge,
        code_challenge_method="S256",
    )


@router.get("/google/callback", name="google_callback", response_class=RedirectResponse)
async def google_callback(request: Request, db: SessionDep) -> RedirectResponse:
    try:
        google = auth_service.get_google_client()
        verifier = request.session.pop("oauth_code_verifier", None)
        token = await google.authorize_access_token(request, code_verifier=verifier)
    except auth_service.GoogleOAuthNotConfiguredError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth is not configured",
        ) from None
    except OAuthError:
        _record_auth_failure(db, "oauth_error")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "GOOGLE_AUTH_FAILED",
                "message": "Google authentication failed",
            },
        ) from None

    nonce = request.session.pop("oauth_nonce", None)
    if not nonce:
        _record_auth_failure(db, "state_invalid")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "GOOGLE_STATE_INVALID",
                "message": "Google authentication failed",
            },
        )
    userinfo = None
    if token.get("id_token"):
        try:
            userinfo = await google.parse_id_token(token, nonce=nonce)
        except Exception:
            userinfo = None
    if not userinfo:
        userinfo = token.get("userinfo")
    if not userinfo or not userinfo.get("sub") or not userinfo.get("email"):
        _record_auth_failure(db, "identity_invalid")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "GOOGLE_IDENTITY_INVALID",
                "message": "Google did not return a usable identity",
            },
        )
    if nonce and userinfo.get("nonce") not in (None, nonce):
        _record_auth_failure(db, "nonce_invalid")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "GOOGLE_NONCE_INVALID",
                "message": "Google authentication failed",
            },
        )
    if not userinfo.get("email_verified"):
        _record_auth_failure(db, "email_unverified")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "GOOGLE_EMAIL_UNVERIFIED",
                "message": "Google authentication failed",
            },
        )

    try:
        user = user_service.authenticate_google_user(
            db,
            google_subject=str(userinfo["sub"]),
            name=str(userinfo.get("name") or ""),
            email=str(userinfo["email"]),
        )
    except user_service.UserAlreadyExistsError:
        _record_auth_failure(db, "user_exists")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "USER_EXISTS", "message": "Google authentication failed"},
        ) from None
    except user_service.GoogleIdentityConflictError:
        _record_auth_failure(db, "identity_conflict")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "GOOGLE_IDENTITY_CONFLICT",
                "message": "Google authentication failed",
            },
        ) from None
    request.session.clear()
    response = RedirectResponse(
        url=settings.auth_success_redirect_uri, status_code=status.HTTP_303_SEE_OTHER
    )
    try:
        session_id, refresh_token, _ = session_service.create_session(
            db,
            user.id,
            user_agent=request.headers.get("user-agent"),
            ip_address=request.client.host if request.client else None,
        )
        token = create_access_token(user.id, session_id)
    except RuntimeError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="JWT authentication is not configured",
        ) from None
    set_auth_cookie(response, token)
    set_refresh_cookie(response, refresh_token)
    set_csrf_cookie(response)
    return response


@router.get("/me", response_model=UserResponse)
def me(user: CurrentUserDep) -> User:
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, db: SessionDep, _: CsrfDep) -> Response:
    request.session.clear()
    session_service.revoke_token(db, request.cookies.get(settings.refresh_cookie_name))
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_auth_cookie(response)
    return response


@router.post("/refresh", status_code=status.HTTP_204_NO_CONTENT)
def refresh(request: Request, db: SessionDep, _: CsrfDep) -> Response:
    refresh_token = request.cookies.get(settings.refresh_cookie_name)
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "AUTH_REQUIRED", "message": "Authentication required"},
        )
    try:
        session_id, new_refresh_token, session = session_service.rotate_session(
            db,
            refresh_token,
            user_agent=request.headers.get("user-agent"),
            ip_address=request.client.host if request.client else None,
        )
    except session_service.RefreshSessionError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "REFRESH_INVALID", "message": "Authentication required"},
        ) from None
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    set_auth_cookie(response, create_access_token(session.user_id, session_id))
    set_refresh_cookie(response, new_refresh_token)
    set_csrf_cookie(response, request.cookies.get(settings.csrf_cookie_name))
    return response


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
def logout_all(user: CurrentUserDep, db: SessionDep, _: CsrfDep) -> Response:
    session_service.revoke_all(db, user.id)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_auth_cookie(response)
    return response


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_me(user: CurrentUserDep, db: SessionDep, _: CsrfDep) -> Response:
    user_service.ensure_user_deletable(db, user.id)
    ledger_service.delete_owner_data(db, user.id)
    session_service.revoke_all(db, user.id)
    user_service.delete_user(db, user.id, actor_user_id=user.id)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_auth_cookie(response)
    return response


def _record_auth_failure(db: SessionDep, reason: str) -> None:
    try:
        add_event(
            db,
            action="auth.google_failure",
            entity_type="authentication",
            metadata={"reason": reason},
        )
        db.commit()
    except Exception:
        db.rollback()
