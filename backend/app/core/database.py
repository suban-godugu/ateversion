import ssl
from collections.abc import AsyncGenerator
from urllib.parse import urlparse

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


def _render_ssl_context() -> ssl.SSLContext:
    # Render Postgres presents a self-signed cert; require TLS but skip verify.
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _connect_args(database_url: str) -> dict:
    if database_url.startswith("sqlite"):
        return {"check_same_thread": False}
    host = (urlparse(database_url).hostname or "").lower()
    if "render.com" in host or host.startswith("dpg-"):
        return {"ssl": _render_ssl_context()}
    if "ssl=require" in database_url or "sslmode=require" in database_url:
        return {"ssl": _render_ssl_context()}
    return {}


settings = get_settings()
engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=not settings.database_url.startswith("sqlite"),
    connect_args=_connect_args(settings.database_url),
)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session


async def reset_schema() -> None:
    """Drop and recreate public schema (Postgres). Used for one-time Render boots."""
    from sqlalchemy import text

    if settings.database_url.startswith("sqlite"):
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        return
    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
        await conn.execute(text("GRANT ALL ON SCHEMA public TO public"))


async def init_db(*, reset: bool = False) -> None:
    """Create schema from SQLAlchemy metadata (Alembic is source of truth for upgrades)."""
    from app import models  # noqa: F401

    if reset:
        await reset_schema()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
