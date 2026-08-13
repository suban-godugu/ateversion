from contextlib import asynccontextmanager
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.api import api_router
from app.api.auth import ensure_seed_users
from app.core.config import get_settings
from app.core.database import SessionLocal, init_db
from app.core.logging import setup_logging
from app.core.redis import close_redis, ping_redis
from app.middleware.request_log import RequestContextMiddleware
from app.websocket.gateway import router as ws_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    setup_logging(settings.log_level)
    # One-time: set RESET_SCHEMA_ON_BOOT=true when reusing an incompatible Postgres.
    reset = os.environ.get("RESET_SCHEMA_ON_BOOT", "").lower() in {"1", "true", "yes"}
    await init_db(reset=reset)
    async with SessionLocal() as db:
        await ensure_seed_users(db)

    # Full demo seed only when explicitly requested (avoids Render boot crashes)
    if os.environ.get("RUN_SEED_ON_BOOT", "").lower() in {"1", "true", "yes"}:
        try:
            from app.ingestion.seed import seed

            await seed()
        except Exception as exc:
            setup_logging(settings.log_level)
            from app.core.logging import get_logger

            get_logger("startup").warning("seed_on_boot_failed", extra={"error": str(exc)})

    await ping_redis()
    yield
    await close_redis()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.add_middleware(RequestContextMiddleware)

    origins = settings.cors_origin_list
    allow_credentials = origins != ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_origin_regex=r"https://.*\.vercel\.app",
        allow_credentials=allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router, prefix="/api")
    app.include_router(ws_router)

    @app.get("/")
    async def root():
        return RedirectResponse(url="/docs")

    return app


app = create_app()
