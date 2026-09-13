from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "My FastAPI App"
    app_version: str = "0.1.0"
    environment: Literal["development", "testing", "production"] = "development"
    api_v1_prefix: str = "/api/v1"
    database_url: str = "postgresql+psycopg://app:app@localhost:5432/app"
    host: str = "127.0.0.1"
    port: int = Field(default=3001, ge=1, le=65535)
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://127.0.0.1:3001/api/v1/auth/google/callback"
    auth_success_redirect_uri: str = "/api/v1/auth/me"
    jwt_secret_key: str = Field(default="", min_length=32)
    jwt_expire_minutes: int = Field(default=15, gt=0)
    refresh_expire_days: int = Field(default=30, gt=0)
    auth_cookie_name: str = "access_token"
    refresh_cookie_name: str = "refresh_token"
    csrf_cookie_name: str = "csrf_token"
    upload_dir: str = "data/uploads"
    cors_allowed_origins: str = ""
    auth_rate_limit_per_minute: int = Field(default=60, gt=0)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
