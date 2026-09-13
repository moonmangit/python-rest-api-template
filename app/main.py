from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.core.config import settings
from app.core.database import Base, engine
from app.core.rate_limit import AuthRateLimitMiddleware
from app.features.auth.domain.model import (  # noqa: F401
    ApplicationGrant,
    AuditEvent,
    RefreshSession,
)
from app.features.router import router as features_router
from app.features.spending_ledger.domain.model import (  # noqa: F401
    Attachment,
    Category,
    IdempotencyKey,
    LedgerRecord,
)
from app.features.users.domain import User  # noqa: F401
from app.shared.health import router as health_router


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    Base.metadata.create_all(bind=engine)
    yield


docs_enabled = settings.environment != "production"
if settings.environment == "production" and len(settings.jwt_secret_key) < 32:
    raise RuntimeError(
        "JWT_SECRET_KEY must be set to at least 32 characters in production"
    )
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs" if docs_enabled else None,
    redoc_url="/redoc" if docs_enabled else None,
    openapi_url="/openapi.json" if docs_enabled else None,
)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.jwt_secret_key or "development-only-oauth-state-key",
    https_only=settings.environment == "production",
    same_site="lax",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in settings.cors_allowed_origins.split(",")
        if origin.strip()
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-CSRF-Token", "Idempotency-Key"],
)
app.add_middleware(AuthRateLimitMiddleware, limit=settings.auth_rate_limit_per_minute)
app.include_router(health_router)
app.include_router(features_router, prefix=settings.api_v1_prefix)


@app.get("/")
def read_root() -> dict[str, str]:
    return {"message": "Hello World"}
