from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthUser, require_permissions
from app.core.database import get_db
from app.core.rbac import Permission
from app.ml.predictive_maintenance.models import PredictRequest
from app.ml.predictive_maintenance.predictor import get_model
from app.ml.predictive_maintenance.service import PredictiveMaintenanceService
from app.schemas.api import (
    MaintenanceAssetOut,
    MaintenanceHealthPoint,
    MaintenanceHistoryItem,
    MaintenanceOut,
    MaintenancePredictResponse,
    MaintenanceTesterDetail,
)

router = APIRouter(tags=["maintenance"])
_svc = PredictiveMaintenanceService()


def _to_asset_out(p) -> MaintenanceAssetOut:
    return MaintenanceAssetOut(
        asset_id=f"{p.tester_id}:{p.component}",
        name=f"{p.tester_id} - {p.component}",
        health_pct=p.health_score,
        status="unavailable"
        if not p.model_available or p.severity.value == "unavailable"
        else ("warn" if p.severity.value in {"watch", "warning", "critical"} else "ok"),
        rul_days=p.rul_days,
        tester_id=p.tester_id,
        component=p.component,
        failure_probability=p.failure_probability,
        confidence=p.confidence,
        severity=p.severity.value,  # type: ignore[arg-type]
        recommended_action=p.recommended_action,
        model_available=p.model_available,
        message=p.message,
        updated_at=p.timestamp,
    )


@router.get("/maintenance", response_model=MaintenanceOut)
async def list_maintenance(
    db: AsyncSession = Depends(get_db),
    _: AuthUser = Depends(require_permissions(Permission.READ_MAINTENANCE)),
) -> MaintenanceOut:
    preds = await _svc.list_predictions(db)
    assets = [_to_asset_out(p) for p in preds]
    flagged = sum(1 for a in assets if a.severity in {"warning", "critical"})
    model_ok = get_model().ensure_ready()
    return MaintenanceOut(flagged_count=flagged, model_available=model_ok, assets=assets)


@router.get("/maintenance/{tester_id}", response_model=MaintenanceTesterDetail)
async def maintenance_tester(
    tester_id: str,
    db: AsyncSession = Depends(get_db),
    _: AuthUser = Depends(require_permissions(Permission.READ_MAINTENANCE)),
) -> MaintenanceTesterDetail:
    health = await _svc.get_tester_health(db, tester_id)
    if health is None:
        raise HTTPException(status_code=404, detail="Tester not found")
    hist = await _svc.history(db, tester_id)
    series = await _svc.health_series(db, tester_id)
    components = [
        MaintenanceAssetOut(
            asset_id=f"{c.tester_id}:{c.component}",
            name=f"{c.tester_id} - {c.component}",
            health_pct=c.health_score,
            status="unavailable"
            if not c.model_available
            else ("warn" if c.severity.value in {"watch", "warning", "critical"} else "ok"),
            rul_days=c.rul_days,
            tester_id=c.tester_id,
            component=c.component,
            failure_probability=c.failure_probability,
            confidence=c.confidence,
            severity=c.severity.value,  # type: ignore[arg-type]
            recommended_action=c.recommended_action,
            model_available=c.model_available,
            message=c.message,
            updated_at=c.timestamp,
        )
        for c in health.components
    ]
    return MaintenanceTesterDetail(
        tester_id=health.tester_id,
        name=health.name,
        status=health.status,
        site_id=health.site_id,
        overall_severity=health.overall_severity.value,  # type: ignore[arg-type]
        model_available=health.model_available,
        components=components,
        history=[
            MaintenanceHistoryItem(
                history_id=h.history_id,
                tester_id=h.tester_id,
                component=h.component,
                event_type=h.event_type,
                detail=h.detail,
                health_score=h.health_score,
                severity=h.severity,
                created_at=h.created_at,
            )
            for h in hist
        ],
        health_series=[
            MaintenanceHealthPoint(
                timestamp=s.created_at,
                health_score=s.health_score,
                failure_probability=s.failure_probability,
                rul_days=s.rul_days,
                severity=s.severity,
                component=s.component,
            )
            for s in series
        ],
    )


@router.post("/maintenance/predict", response_model=MaintenancePredictResponse)
async def predict_maintenance(
    body: PredictRequest,
    db: AsyncSession = Depends(get_db),
    _: AuthUser = Depends(require_permissions(Permission.RUN_MAINTENANCE_PREDICT)),
) -> MaintenancePredictResponse:
    preds = await _svc.run_predict(db, body)
    return MaintenancePredictResponse(predictions=[_to_asset_out(p) for p in preds])
