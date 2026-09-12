from authlib.integrations.starlette_client import OAuth

from app.core.config import settings


class GoogleOAuthNotConfiguredError(RuntimeError):
    """Raised when Google OAuth credentials are not configured."""


oauth = OAuth()
if settings.google_client_id and settings.google_client_secret:
    oauth.register(
        name="google",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )


def get_google_client():
    client = oauth.create_client("google")
    if client is None:
        raise GoogleOAuthNotConfiguredError
    return client
