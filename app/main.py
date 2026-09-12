from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import DEVELOPMENT_JWT_SECRET, settings
from app.core.database import Base, SessionLocal, engine
from app.features.router import router as features_router
from app.features.todo.domain import model as _todo_model  # noqa: F401
from app.features.user.application.service import ensure_admin
from app.features.user.domain import User  # noqa: F401
from app.shared.health import router as health_router


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    if (
        settings.environment == "production"
        and settings.jwt_secret_key == DEVELOPMENT_JWT_SECRET
    ):
        raise RuntimeError("JWT_SECRET_KEY must be changed in production")
    Base.metadata.create_all(bind=engine)
    if settings.admin_username and settings.admin_password:
        with SessionLocal() as db:
            ensure_admin(
                db,
                username=settings.admin_username,
                password=settings.admin_password,
            )
    yield


docs_enabled = settings.environment != "production"
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs" if docs_enabled else None,
    redoc_url="/redoc" if docs_enabled else None,
    openapi_url="/openapi.json" if docs_enabled else None,
)
app.include_router(health_router)
app.include_router(features_router, prefix=settings.api_v1_prefix)


@app.get("/")
def read_root() -> dict[str, str]:
    return {"message": "Hello World"}
