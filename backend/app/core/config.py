from __future__ import annotations

import os
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def normalize_database_url(url: str) -> str:
    """Convert hosted provider URLs to SQLAlchemy async drivers."""
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    if url.startswith("postgresql://") and "+asyncpg" not in url and "+psycopg" not in url:
        url = "postgresql+asyncpg://" + url[len("postgresql://") :]
    # Prefer connect_args ssl=True; strip query flags that confuse asyncpg
    for token in ("?sslmode=require", "&sslmode=require", "?ssl=require", "&ssl=require",
                  "?sslmode=prefer", "&sslmode=prefer"):
        url = url.replace(token, "")
    if url.endswith("?") or url.endswith("&"):
        url = url[:-1]
    return url


def _default_database_url() -> str:
    # Hugging Face Spaces: prefer persistent /data when available
    if os.environ.get("SPACE_ID") or os.environ.get("SPACE_HOST"):
        data_dir = "/data" if os.path.isdir("/data") else "/tmp"
        return f"sqlite+aiosqlite:///{data_dir}/wafer_yield.db"
    return "sqlite+aiosqlite:///./wafer_yield.db"


def _default_redis_url() -> str:
    # Single-container Spaces: in-process bus (no external Redis required)
    if os.environ.get("SPACE_ID") or os.environ.get("SPACE_HOST"):
        return "memory://"
    return "redis://127.0.0.1:6379/0"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = _default_database_url()
    redis_url: str = _default_redis_url()
    cors_origins: str = "*"
    telemetry_channel: str = "test-floor.events"
    wafer_dataset_root: str = ""
    host: str = "0.0.0.0"
    port: int = 7860
    app_name: str = "Wafer Yield Intelligence API"

    jwt_secret: str = "dev-change-me-wafer-yield-jwt-secret-32chars"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480
    auth_disabled: bool = False

    rate_limit_per_minute: int = 120
    stale_telemetry_seconds: int = 45
    log_level: str = "INFO"

    @field_validator("database_url", mode="before")
    @classmethod
    def _async_db_url(cls, value: object) -> object:
        if isinstance(value, str) and value:
            return normalize_database_url(value)
        return value

    @property
    def use_memory_bus(self) -> bool:
        url = (self.redis_url or "").lower()
        return url in {"", "memory", "memory://", "local", "local://", "none"}

    @property
    def cors_origin_list(self) -> list[str]:
        raw = [o.strip() for o in self.cors_origins.split(",") if o.strip()]
        return raw if raw else ["*"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
