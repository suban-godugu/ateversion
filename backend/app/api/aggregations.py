from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthUser, require_permissions
from app.core.database import get_db
from app.core.rbac import Permission
from app.repositories import PageParams, SortParams
from app.services.aggregation_service import AggregationService

router = APIRouter(tags=["aggregations"])


@router.get("/aggregations/wafer-yield")
async def wafer_yield_agg(
    lot_id: str | None = None,
    tester_id: str | None = None,
    site_id: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    db: AsyncSession = Depends(get_db),
    _: AuthUser = Depends(require_permissions(Permission.READ_AGGREGATIONS)),
) -> dict:
    return await AggregationService(db).wafer_yield(
        lot_id=lot_id, tester_id=tester_id, site_id=site_id, since=since, until=until
    )


@router.get("/aggregations/lots")
async def lots_agg(
    tester_id: str | None = None,
    site_id: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    db: AsyncSession = Depends(get_db),
    _: AuthUser = Depends(require_permissions(Permission.READ_AGGREGATIONS)),
) -> dict:
    return await AggregationService(db).lots(
        tester_id=tester_id, site_id=site_id, since=since, until=until
    )


@router.get("/aggregations/testers")
async def testers_agg(
    site_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    _: AuthUser = Depends(require_permissions(Permission.READ_AGGREGATIONS)),
) -> dict:
    return await AggregationService(db).testers(site_id=site_id)


@router.get("/aggregations/sites/{site_id}")
async def site_agg(
    site_id: str,
    since: datetime | None = None,
    until: datetime | None = None,
    db: AsyncSession = Depends(get_db),
    _: AuthUser = Depends(require_permissions(Permission.READ_AGGREGATIONS)),
) -> dict:
    return await AggregationService(db).site_rollup(site_id, since=since, until=until)


@router.get("/aggregations/kpis/{metric_id}/history")
async def kpi_history_agg(
    metric_id: str,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _: AuthUser = Depends(require_permissions(Permission.READ_AGGREGATIONS)),
) -> dict:
    points = await AggregationService(db).kpi_history(
        metric_id, since=since, until=until, limit=limit
    )
    return {"metric_id": metric_id, "history": points}


@router.get("/aggregations/wafers")
async def wafers_page(
    lot_id: str | None = None,
    tester_id: str | None = None,
    site_id: str | None = None,
    status: str | None = None,
    sort: str = Query("updated_at"),
    direction: str = Query("desc"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: AuthUser = Depends(require_permissions(Permission.READ_AGGREGATIONS)),
) -> dict:
    page = await AggregationService(db).list_wafers_page(
        lot_id=lot_id,
        tester_id=tester_id,
        site_id=site_id,
        status=status,
        sort=SortParams(field=sort, direction=direction),
        page=PageParams(limit=limit, offset=offset),
    )
    return {
        "total": page.total,
        "limit": page.limit,
        "offset": page.offset,
        "items": [
            {
                "wafer_id": w.wafer_id,
                "lot_id": w.lot_id,
                "tester_id": w.tester_id,
                "site_id": w.site_id,
                "status": w.status,
                "yield_pct": w.yield_pct,
                "tested_dies": w.tested_dies,
                "total_dies": w.total_dies,
                "updated_at": w.updated_at,
            }
            for w in page.items
        ],
    }
