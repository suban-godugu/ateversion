from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthUser, require_permissions
from app.core.database import get_db
from app.core.rbac import Permission
from app.schemas.api import (
    DashboardSummary,
    DieOut,
    TesterOut,
    WaferDetail,
    WaferListItem,
)
from app.services import dashboard_service as svc

router = APIRouter()


@router.get("/dashboard/summary", response_model=DashboardSummary)
async def dashboard_summary(
    db: AsyncSession = Depends(get_db),
    _: AuthUser = Depends(require_permissions(Permission.READ_DASHBOARD)),
) -> DashboardSummary:
    return await svc.get_summary(db)


@router.get("/wafers", response_model=list[WaferListItem])
async def wafers(
    db: AsyncSession = Depends(get_db),
    _: AuthUser = Depends(require_permissions(Permission.READ_WAFER)),
) -> list[WaferListItem]:
    return await svc.list_wafers(db)


@router.get("/wafers/{wafer_id}", response_model=WaferDetail)
async def wafer_detail(
    wafer_id: str,
    db: AsyncSession = Depends(get_db),
    _: AuthUser = Depends(require_permissions(Permission.READ_WAFER)),
) -> WaferDetail:
    detail = await svc.get_wafer(db, wafer_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Wafer not found")
    return detail


@router.get("/wafers/{wafer_id}/dies", response_model=list[DieOut])
async def wafer_dies(
    wafer_id: str,
    db: AsyncSession = Depends(get_db),
    _: AuthUser = Depends(require_permissions(Permission.READ_WAFER)),
) -> list[DieOut]:
    return await svc.get_dies(db, wafer_id)


@router.get("/testers", response_model=list[TesterOut])
async def testers(
    db: AsyncSession = Depends(get_db),
    _: AuthUser = Depends(require_permissions(Permission.READ_DASHBOARD)),
) -> list[TesterOut]:
    return await svc.get_testers(db)
