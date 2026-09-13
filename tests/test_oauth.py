import asyncio

import pytest
from fastapi import HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from starlette.requests import Request

from app.core.config import settings
from app.features.auth.application import service as auth_service
from app.features.auth.presentation.router import google_callback, google_login
from app.features.users.domain import User, UserRole


def _request(session: dict | None = None) -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/v1/auth/google/callback",
        "headers": [(b"host", b"testserver")],
        "query_string": b"code=abc&state=state",
        "scheme": "http",
        "server": ("testserver", 80),
        "client": ("127.0.0.1", 1234),
        "session": session if session is not None else {},
    }
    return Request(scope)


class FakeGoogleClient:
    def __init__(self, claims: dict | None = None) -> None:
        self.claims = claims or {}
        self.authorize_kwargs = None
        self.code_verifier = None

    async def authorize_redirect(self, request, redirect_uri, **kwargs):
        self.authorize_kwargs = kwargs
        return RedirectResponse(redirect_uri)

    async def authorize_access_token(self, request, **kwargs):
        self.code_verifier = kwargs.get("code_verifier")
        return {"id_token": "id-token"}

    async def parse_id_token(self, token, nonce):
        assert token["id_token"] == "id-token"
        assert nonce == "nonce"
        return self.claims | {"nonce": nonce}


class InvalidIdTokenClient(FakeGoogleClient):
    async def authorize_access_token(self, request, **kwargs):
        self.code_verifier = kwargs.get("code_verifier")
        return {
            "id_token": "invalid-id-token",
            "userinfo": {
                "sub": "google-subject",
                "email": "person@example.com",
                "email_verified": True,
            },
        }

    async def parse_id_token(self, token, nonce):
        raise ValueError("invalid ID token")


def test_google_login_generates_state_nonce_and_pkce(db, monkeypatch) -> None:
    client = FakeGoogleClient()
    monkeypatch.setattr(auth_service, "get_google_client", lambda: client)
    request = _request()

    response = asyncio.run(google_login(request, db))

    assert response.status_code == 307
    assert request.session["oauth_nonce"]
    assert request.session["oauth_code_verifier"]
    assert client.authorize_kwargs["code_challenge_method"] == "S256"
    assert client.authorize_kwargs["code_challenge"]


def test_google_callback_validates_identity_and_sets_all_session_cookies(
    db, monkeypatch
) -> None:
    monkeypatch.setattr(
        settings, "jwt_secret_key", "test-jwt-secret-32-bytes-long-value"
    )
    client = FakeGoogleClient(
        {
            "sub": "google-subject",
            "email": "person@example.com",
            "email_verified": True,
            "name": "Person",
        }
    )
    monkeypatch.setattr(auth_service, "get_google_client", lambda: client)
    request = _request({"oauth_nonce": "nonce", "oauth_code_verifier": "verifier"})

    response = asyncio.run(google_callback(request, db))

    assert response.status_code == 303
    assert client.code_verifier == "verifier"
    cookie = b"\n".join(
        value for key, value in response.raw_headers if key == b"set-cookie"
    ).decode()
    assert "access_token=" in cookie
    assert "refresh_token=" in cookie
    assert "csrf_token=" in cookie
    user = db.scalar(select(User).where(User.google_subject == "google-subject"))
    assert user.role == UserRole.ADMIN


def test_google_callback_rejects_missing_oauth_state(db, monkeypatch) -> None:
    monkeypatch.setattr(auth_service, "get_google_client", FakeGoogleClient)
    request = _request()

    with pytest.raises(HTTPException) as error:
        asyncio.run(google_callback(request, db))

    assert error.value.status_code == 400
    assert error.value.detail["code"] == "GOOGLE_STATE_INVALID"


def test_google_callback_rejects_invalid_id_token_instead_of_using_userinfo(
    db, monkeypatch
) -> None:
    client = InvalidIdTokenClient()
    monkeypatch.setattr(auth_service, "get_google_client", lambda: client)
    request = _request({"oauth_nonce": "nonce", "oauth_code_verifier": "verifier"})

    with pytest.raises(HTTPException) as error:
        asyncio.run(google_callback(request, db))

    assert error.value.status_code == 400
    assert error.value.detail["code"] == "GOOGLE_IDENTITY_INVALID"
    assert db.query(User).count() == 0


def test_google_callback_rejects_missing_pkce_verifier(db, monkeypatch) -> None:
    monkeypatch.setattr(auth_service, "get_google_client", FakeGoogleClient)
    request = _request({"oauth_nonce": "nonce"})

    with pytest.raises(HTTPException) as error:
        asyncio.run(google_callback(request, db))

    assert error.value.status_code == 400
    assert error.value.detail["code"] == "GOOGLE_PKCE_INVALID"
