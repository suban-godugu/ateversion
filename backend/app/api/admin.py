"""Admin-only bootstrap helpers for empty production databases."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import ensure_seed_users
from app.api.deps import AuthUser, require_permissions
from app.core.database import SessionLocal, get_db
from app.core.rbac import Permission
from app.ingestion.seed import seed
from app.models.entities import Die, KpiMetric, Wafer
from app.repositories.event_repo import AuditLogRepository

router = APIRouter(tags=["admin"])


@router.post("/admin/seed")
async def bootstrap_seed(
    _: AsyncSession = Depends(get_db),
    user: AuthUser = Depends(require_permissions(Permission.MANAGE_USERS)),
) -> dict:
    """
    Populate an empty/reset production DB with reference floor data.
    ADMIN only. Safe to re-run (clears domain tables then reseeds).
    """
    await seed()
    async with SessionLocal() as db:
        await ensure_seed_users(db)
        await AuditLogRepository(db).write(
            actor=user.username,
            action="bootstrap_seed",
            entity_type="database",
            entity_id="production",
            detail="Admin triggered reference seed",
        )
        await db.commit()
        wafers = int((await db.scalar(select(func.count()).select_from(Wafer))) or 0)
        dies = int((await db.scalar(select(func.count()).select_from(Die))) or 0)
        kpis = int((await db.scalar(select(func.count()).select_from(KpiMetric))) or 0)
    return {
        "status": "seeded",
        "wafers": wafers,
        "dies": dies,
        "kpis": kpis,
        "actor": user.username,
    }
