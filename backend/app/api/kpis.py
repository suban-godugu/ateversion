from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthUser, require_permissions
from app.core.database import get_db
from app.core.rbac import Permission
from app.schemas.api import KpiDetailOut, KpiHistoryOut, KpisListOut
from app.services import kpi_service

router = APIRouter(tags=["kpis"])


@router.get("/kpis", response_model=KpisListOut)
async def list_kpis(
    db: AsyncSession = Depends(get_db),
    _: AuthUser = Depends(require_permissions(Permission.READ_KPIS)),
) -> KpisListOut:
    return await kpi_service.list_kpis(db)


@router.get("/kpis/{kpi_id}", response_model=KpiDetailOut)
async def get_kpi(
    kpi_id: str,
    db: AsyncSession = Depends(get_db),
    _: AuthUser = Depends(require_permissions(Permission.READ_KPIS)),
) -> KpiDetailOut:
    detail = await kpi_service.get_kpi(db, kpi_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="KPI not found")
    return detail


@router.get("/kpis/{kpi_id}/history", response_model=KpiHistoryOut)
async def get_kpi_history(
    kpi_id: str,
    limit: int = Query(48, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _: AuthUser = Depends(require_permissions(Permission.READ_KPIS)),
) -> KpiHistoryOut:
    hist = await kpi_service.get_kpi_history(db, kpi_id, limit=limit)
    if hist is None:
        raise HTTPException(status_code=404, detail="KPI not found")
    return hist
