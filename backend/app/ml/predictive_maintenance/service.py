from __future__ import annotations

import json
from datetime import datetime
from uuid import uuid4

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.redis import publish_event
from app.ml.predictive_maintenance.models import (
    HealthSeverity,
    MaintenancePrediction,
    PredictRequest,
    TelemetryFeature,
    TesterHealth,
)
from app.ml.predictive_maintenance.predictor import get_model
from app.ml.predictive_maintenance.recommendations import (
    build_recommendation,
    severity_from_prediction,
)
from app.models.entities import (
    MaintenanceAsset,
    MaintenanceHistory,
    MaintenancePredictionRow,
    TelemetryFeatureRow,
    Tester,
)
from app.schemas.events import EventType, TelemetryEvent


class PredictiveMaintenanceService:
    def __init__(self) -> None:
        self.model = get_model()

    async def latest_features(
        self, db: AsyncSession, tester_id: str, component: str | None = None
    ) -> TelemetryFeature | None:
        q = select(TelemetryFeatureRow).where(TelemetryFeatureRow.tester_id == tester_id)
        if component:
            q = q.where(TelemetryFeatureRow.component == component)
        q = q.order_by(desc(TelemetryFeatureRow.captured_at)).limit(1)
        row = (await db.execute(q)).scalar_one_or_none()
        if row is None:
            return None
        return TelemetryFeature(
            tester_id=row.tester_id,
            component=row.component,
            test_failures=row.test_failures,
            parametric_drift=row.parametric_drift,
            contact_resistance=row.contact_resistance,
            temperature=row.temperature,
            voltage_deviation=row.voltage_deviation,
            current_deviation=row.current_deviation,
            cycle_count=row.cycle_count,
            historical_failures=row.historical_failures,
            maintenance_events=row.maintenance_events,
            tester_utilization=row.tester_utilization,
            captured_at=row.captured_at,
        )

    def predict_from_features(
        self,
        features: TelemetryFeature,
        *,
        tester_online: bool = True,
    ) -> MaintenancePrediction:
        ts = datetime.utcnow()
        model_ok = self.model.ensure_ready()
        if not model_ok:
            return MaintenancePrediction(
                tester_id=features.tester_id,
                component=features.component,
                health_score=None,
                failure_probability=None,
                rul_days=None,
                severity=HealthSeverity.unavailable,
                confidence=None,
                recommended_action=None,
                recommendation=None,
                timestamp=ts,
                model_available=False,
                message="Prediction unavailable",
            )

        out = self.model.predict(features)
        severity = severity_from_prediction(
            health_score=out["health_score"],  # type: ignore[arg-type]
            failure_probability=out["failure_probability"],  # type: ignore[arg-type]
            rul_days=out["rul_days"],  # type: ignore[arg-type]
            tester_online=tester_online,
            model_available=True,
        )
        rec = build_recommendation(
            features,
            health_score=out["health_score"],  # type: ignore[arg-type]
            failure_probability=out["failure_probability"],  # type: ignore[arg-type]
            rul_days=out["rul_days"],  # type: ignore[arg-type]
            severity=severity,
        )
        return MaintenancePrediction(
            tester_id=features.tester_id,
            component=features.component,
            health_score=out["health_score"],  # type: ignore[arg-type]
            failure_probability=out["failure_probability"],  # type: ignore[arg-type]
            rul_days=out["rul_days"],  # type: ignore[arg-type]
            severity=severity,
            confidence=out["confidence"],  # type: ignore[arg-type]
            recommended_action=rec.action if rec else None,
            recommendation=rec,
            timestamp=ts,
            model_available=True,
            message=None if severity != HealthSeverity.unavailable else "Prediction unavailable",
        )

    async def persist_prediction(
        self, db: AsyncSession, prediction: MaintenancePrediction, features: TelemetryFeature
    ) -> None:
        row = MaintenancePredictionRow(
            prediction_id=str(uuid4()),
            tester_id=prediction.tester_id,
            component=prediction.component,
            health_score=prediction.health_score,
            failure_probability=prediction.failure_probability,
            rul_days=prediction.rul_days,
            severity=prediction.severity.value,
            confidence=prediction.confidence,
            recommended_action=prediction.recommended_action,
            recommendation_json=prediction.recommendation.model_dump() if prediction.recommendation else None,
            model_available=prediction.model_available,
            message=prediction.message,
            features_json=features.model_dump(mode="json"),
            created_at=prediction.timestamp,
        )
        db.add(row)

        asset_id = f"{prediction.tester_id}:{prediction.component}"
        asset = await db.get(MaintenanceAsset, asset_id)
        if asset is None:
            asset = MaintenanceAsset(
                asset_id=asset_id,
                name=f"{prediction.tester_id} - {prediction.component}",
                tester_id=prediction.tester_id,
                component=prediction.component,
            )
            db.add(asset)
        asset.health_pct = prediction.health_score if prediction.health_score is not None else asset.health_pct
        asset.rul_days = prediction.rul_days
        asset.failure_probability = prediction.failure_probability
        asset.confidence = prediction.confidence
        asset.severity = prediction.severity.value
        asset.recommended_action = prediction.recommended_action
        asset.model_available = prediction.model_available
        asset.status = (
            "warn"
            if prediction.severity in {HealthSeverity.warning, HealthSeverity.critical, HealthSeverity.watch}
            else "ok"
        )
        if prediction.severity == HealthSeverity.unavailable:
            asset.status = "unavailable"
        asset.updated_at = prediction.timestamp

        hist = MaintenanceHistory(
            history_id=str(uuid4()),
            tester_id=prediction.tester_id,
            component=prediction.component,
            event_type="prediction",
            detail=prediction.recommended_action or prediction.message or prediction.severity.value,
            health_score=prediction.health_score,
            severity=prediction.severity.value,
            created_at=prediction.timestamp,
        )
        db.add(hist)
        await db.flush()

    async def publish_prediction(self, prediction: MaintenancePrediction) -> None:
        settings = get_settings()
        event = TelemetryEvent(
            event_id=str(uuid4()),
            event_type=EventType.predictive_maintenance,
            timestamp=prediction.timestamp,
            source="ml",
            tester_id=prediction.tester_id,
            site_id=None,
            lot_id=None,
            wafer_id=None,
            die_id=None,
            sequence_number=int(prediction.timestamp.timestamp()),
            payload={
                "asset_id": f"{prediction.tester_id}:{prediction.component}",
                "asset_name": f"{prediction.tester_id} - {prediction.component}",
                "component": prediction.component,
                "health_pct": prediction.health_score,
                "health_score": prediction.health_score,
                "failure_probability": prediction.failure_probability,
                "rul_days": prediction.rul_days,
                "severity": prediction.severity.value,
                "confidence": prediction.confidence,
                "recommended_action": prediction.recommended_action,
                "model_available": prediction.model_available,
                "message": prediction.message,
                "status": "warn"
                if prediction.severity.value in {"watch", "warning", "critical"}
                else "ok",
            },
        )
        await publish_event(
            settings.telemetry_channel,
            json.dumps({"kind": "telemetry_event", "event": json.loads(event.model_dump_json())}),
        )

    async def run_predict(self, db: AsyncSession, body: PredictRequest) -> list[MaintenancePrediction]:
        results: list[MaintenancePrediction] = []
        if body.features is not None:
            features_list = [body.features]
        else:
            q = select(TelemetryFeatureRow)
            if body.tester_id:
                q = q.where(TelemetryFeatureRow.tester_id == body.tester_id)
            if body.component:
                q = q.where(TelemetryFeatureRow.component == body.component)
            # latest per tester+component
            rows = (await db.execute(q.order_by(desc(TelemetryFeatureRow.captured_at)))).scalars().all()
            seen: set[tuple[str, str]] = set()
            features_list = []
            for row in rows:
                key = (row.tester_id, row.component)
                if key in seen:
                    continue
                seen.add(key)
                features_list.append(
                    TelemetryFeature(
                        tester_id=row.tester_id,
                        component=row.component,
                        test_failures=row.test_failures,
                        parametric_drift=row.parametric_drift,
                        contact_resistance=row.contact_resistance,
                        temperature=row.temperature,
                        voltage_deviation=row.voltage_deviation,
                        current_deviation=row.current_deviation,
                        cycle_count=row.cycle_count,
                        historical_failures=row.historical_failures,
                        maintenance_events=row.maintenance_events,
                        tester_utilization=row.tester_utilization,
                        captured_at=row.captured_at,
                    )
                )

        for features in features_list:
            tester = await db.get(Tester, features.tester_id)
            online = bool(tester and tester.status != "offline")
            prediction = self.predict_from_features(features, tester_online=online)
            await self.persist_prediction(db, prediction, features)
            if body.publish and prediction.model_available:
                await self.publish_prediction(prediction)
            results.append(prediction)

        await db.commit()
        return results

    async def list_predictions(self, db: AsyncSession) -> list[MaintenancePrediction]:
        assets = (await db.execute(select(MaintenanceAsset).order_by(MaintenanceAsset.health_pct))).scalars().all()
        out: list[MaintenancePrediction] = []
        for a in assets:
            severity = HealthSeverity(a.severity) if a.severity in HealthSeverity._value2member_map_ else HealthSeverity.unavailable
            if not a.model_available:
                severity = HealthSeverity.unavailable
            out.append(
                MaintenancePrediction(
                    tester_id=a.tester_id or a.asset_id,
                    component=a.component or a.name,
                    health_score=a.health_pct if a.model_available else None,
                    failure_probability=a.failure_probability if a.model_available else None,
                    rul_days=a.rul_days if a.model_available else None,
                    severity=severity,
                    confidence=a.confidence if a.model_available else None,
                    recommended_action=a.recommended_action if a.model_available else None,
                    recommendation=None,
                    timestamp=a.updated_at,
                    model_available=bool(a.model_available),
                    message=None if a.model_available else "Prediction unavailable",
                )
            )
        return out

    async def get_tester_health(self, db: AsyncSession, tester_id: str) -> TesterHealth | None:
        tester = await db.get(Tester, tester_id)
        if tester is None:
            return None
        assets = (
            await db.execute(select(MaintenanceAsset).where(MaintenanceAsset.tester_id == tester_id))
        ).scalars().all()
        components = []
        model_ok = True
        latest = None
        for a in assets:
            pred = MaintenancePrediction(
                tester_id=tester_id,
                component=a.component or a.name,
                health_score=a.health_pct if a.model_available else None,
                failure_probability=a.failure_probability if a.model_available else None,
                rul_days=a.rul_days if a.model_available else None,
                severity=HealthSeverity(a.severity)
                if a.severity in HealthSeverity._value2member_map_
                else HealthSeverity.unavailable,
                confidence=a.confidence if a.model_available else None,
                recommended_action=a.recommended_action if a.model_available else None,
                recommendation=None,
                timestamp=a.updated_at,
                model_available=bool(a.model_available),
                message=None if a.model_available else "Prediction unavailable",
            )
            if not a.model_available:
                model_ok = False
                pred.severity = HealthSeverity.unavailable
            components.append(pred)
            if latest is None or a.updated_at > latest:
                latest = a.updated_at

        order = [
            HealthSeverity.critical,
            HealthSeverity.warning,
            HealthSeverity.watch,
            HealthSeverity.offline,
            HealthSeverity.unavailable,
            HealthSeverity.healthy,
        ]
        overall = HealthSeverity.healthy
        for sev in order:
            if any(c.severity == sev for c in components):
                overall = sev
                break
        if not components:
            overall = HealthSeverity.unavailable
            model_ok = self.model.ensure_ready()

        return TesterHealth(
            tester_id=tester.tester_id,
            name=tester.name,
            status=tester.status,
            site_id=tester.site_id,
            components=components,
            overall_severity=overall,
            model_available=model_ok,
            latest_timestamp=latest,
        )

    async def history(
        self, db: AsyncSession, tester_id: str, limit: int = 40
    ) -> list[MaintenanceHistory]:
        rows = (
            await db.execute(
                select(MaintenanceHistory)
                .where(MaintenanceHistory.tester_id == tester_id)
                .order_by(desc(MaintenanceHistory.created_at))
                .limit(limit)
            )
        ).scalars().all()
        return list(rows)

    async def health_series(
        self, db: AsyncSession, tester_id: str, limit: int = 40
    ) -> list[MaintenancePredictionRow]:
        rows = (
            await db.execute(
                select(MaintenancePredictionRow)
                .where(MaintenancePredictionRow.tester_id == tester_id)
                .order_by(desc(MaintenancePredictionRow.created_at))
                .limit(limit)
            )
        ).scalars().all()
        return list(reversed(rows))
