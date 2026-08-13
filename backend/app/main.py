from contextlib import asynccontextmanager

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
    await init_db()
    async with SessionLocal() as db:
        await ensure_seed_users(db)
    # Best-effort demo seed on empty Hugging Face Space
    try:
        from sqlalchemy import func, select

        from app.models.entities import Wafer

        async with SessionLocal() as db:
            count = await db.scalar(select(func.count()).select_from(Wafer))
        if not count:
            from app.ingestion.seed import seed

            await seed()
    except Exception:
        pass
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
        allow_credentials=allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router, prefix="/api")
    app.include_router(ws_router)

    @app.get("/")
    async def root():
        # Hugging Face Space iframe / health landing
        return RedirectResponse(url="/docs")

    return app


app = create_app()
