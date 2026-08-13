from fastapi import APIRouter
from sqlalchemy import text

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.redis import ping_redis
from app.schemas.api import HealthOut
from app.websocket.gateway import manager

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthOut)
async def health() -> HealthOut:
    """Liveness — process is up (does not require dependencies)."""
    return HealthOut(
        status="ok",
        database=True,
        redis=True,
        app=get_settings().app_name,
    )


@router.get("/ready")
async def ready() -> dict:
    """Readiness — PostgreSQL + Redis must be reachable."""
    db_ok = False
    db_error = None
    try:
        async with SessionLocal() as session:
            await session.execute(text("SELECT 1"))
            db_ok = True
    except Exception as exc:
        db_error = str(exc)

    redis_ok = await ping_redis()
    ready_ok = db_ok and redis_ok
    settings = get_settings()
    return {
        "status": "ready" if ready_ok else "not_ready",
        "database": db_ok,
        "redis": redis_ok,
        "event_bus": "memory" if settings.use_memory_bus else "redis",
        "websocket_clients": len(manager.active),
        "detail": None if ready_ok else {"database_error": db_error, "redis": redis_ok},
    }
