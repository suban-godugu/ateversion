from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthUser, require_permissions
from app.core.database import get_db
from app.core.rbac import Permission
from app.repositories.event_repo import AuditLogRepository
from app.services.test_limits.models import (
    ApprovalRequest,
    RecommendRequest,
    RejectRequest,
    RollbackRequest,
    TestLimitDetailOut,
    TestLimitsListOut,
)
from app.services.test_limits.service import TestLimitsService

router = APIRouter(tags=["test-limits"])
_svc = TestLimitsService()


@router.get("/test-limits", response_model=TestLimitsListOut)
async def list_test_limits(
    db: AsyncSession = Depends(get_db),
    _: AuthUser = Depends(require_permissions(Permission.READ_LIMITS)),
) -> TestLimitsListOut:
    return await _svc.list_limits(db)


@router.get("/test-limits/{limit_id}", response_model=TestLimitDetailOut)
async def get_test_limit(
    limit_id: str,
    db: AsyncSession = Depends(get_db),
    _: AuthUser = Depends(require_permissions(Permission.READ_LIMITS)),
) -> TestLimitDetailOut:
    return await _svc.get_limit(db, limit_id)


@router.post("/test-limits/{limit_id}/recommend", response_model=TestLimitDetailOut)
async def recommend_test_limit(
    limit_id: str,
    body: RecommendRequest,
    db: AsyncSession = Depends(get_db),
    user: AuthUser = Depends(require_permissions(Permission.RECOMMEND_LIMITS)),
) -> TestLimitDetailOut:
    body.actor = user.username
    result = await _svc.recommend(db, limit_id, body)
    await AuditLogRepository(db).write(
        actor=user.username,
        action="recommend_limit",
        entity_type="dynamic_test_limit",
        entity_id=limit_id,
        detail=result.reason or "recommend",
    )
    await db.commit()
    return result


@router.post("/test-limits/{limit_id}/approve", response_model=TestLimitDetailOut)
async def approve_test_limit(
    limit_id: str,
    body: ApprovalRequest,
    db: AsyncSession = Depends(get_db),
    user: AuthUser = Depends(require_permissions(Permission.APPROVE_LIMITS)),
) -> TestLimitDetailOut:
    body.actor = user.username
    result = await _svc.approve_limit(db, limit_id, body)
    await AuditLogRepository(db).write(
        actor=user.username,
        action="approve_limit",
        entity_type="dynamic_test_limit",
        entity_id=limit_id,
        detail=body.comment or "approved",
    )
    await db.commit()
    return result


@router.post("/test-limits/{limit_id}/reject", response_model=TestLimitDetailOut)
async def reject_test_limit(
    limit_id: str,
    body: RejectRequest,
    db: AsyncSession = Depends(get_db),
    user: AuthUser = Depends(require_permissions(Permission.REJECT_LIMITS)),
) -> TestLimitDetailOut:
    body.actor = user.username
    result = await _svc.reject_limit(db, limit_id, body)
    await AuditLogRepository(db).write(
        actor=user.username,
        action="reject_limit",
        entity_type="dynamic_test_limit",
        entity_id=limit_id,
        detail=body.comment or "rejected",
    )
    await db.commit()
    return result


@router.post("/test-limits/{limit_id}/rollback", response_model=TestLimitDetailOut)
async def rollback_test_limit(
    limit_id: str,
    body: RollbackRequest,
    db: AsyncSession = Depends(get_db),
    user: AuthUser = Depends(require_permissions(Permission.ROLLBACK_LIMITS)),
) -> TestLimitDetailOut:
    body.actor = user.username
    result = await _svc.rollback_limit(db, limit_id, body)
    await AuditLogRepository(db).write(
        actor=user.username,
        action="rollback_limit",
        entity_type="dynamic_test_limit",
        entity_id=limit_id,
        detail=body.comment or "rollback",
    )
    await db.commit()
    return result
