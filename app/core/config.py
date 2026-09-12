from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

DEVELOPMENT_JWT_SECRET = "development-only-change-this-secret-key-32chars"


class Settings(BaseSettings):
    app_name: str = "Todo API"
    app_version: str = "0.1.0"
    environment: Literal["development", "testing", "production"] = "development"
    api_v1_prefix: str = "/api/v1"
    database_url: str = "postgresql+psycopg://app:app@localhost:5432/app"
    host: str = "127.0.0.1"
    port: int = Field(default=3001, ge=1, le=65535)
    jwt_secret_key: str = Field(default=DEVELOPMENT_JWT_SECRET, min_length=32)
    jwt_algorithm: Literal["HS256"] = "HS256"
    jwt_expire_minutes: int = Field(default=30, ge=1, le=1440)
    auth_cookie_name: str = "access_token"
    admin_username: str | None = Field(default=None, min_length=3)
    admin_password: str | None = Field(default=None, min_length=8)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
