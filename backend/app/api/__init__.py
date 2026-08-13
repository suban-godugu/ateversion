from fastapi import APIRouter

from app.api import (
    aggregations,
    auth,
    dashboard,
    events,
    health,
    kpis,
    maintenance,
    telemetry,
    test_limits,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router)
api_router.include_router(telemetry.router, tags=["telemetry"])
api_router.include_router(dashboard.router, tags=["dashboard"])
api_router.include_router(events.router)
api_router.include_router(aggregations.router)
api_router.include_router(kpis.router)
api_router.include_router(maintenance.router)
api_router.include_router(test_limits.router)
