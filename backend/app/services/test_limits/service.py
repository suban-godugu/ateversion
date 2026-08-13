from __future__ import annotations

import json
from datetime import datetime
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.redis import publish_event
from app.models.entities import (
    DashboardState,
    LimitAdjustmentRecord,
    LimitApprovalRecord,
    LimitAuditRecord,
    TestLimitRecord,
)
from app.schemas.events import EventType, TelemetryEvent
from app.services.test_limits.engine import (
    change_label,
    generate_limit_recommendation,
    validate_limit_change,
)
from app.services.test_limits.models import (
    ApprovalRequest,
    LimitAdjustment,
    LimitApproval,
    LimitAudit,
    LimitDirection,
    LimitStatus,
    RecommendRequest,
    RejectRequest,
    RollbackRequest,
    TestLimit,
    TestLimitDetailOut,
    TestLimitsListOut,
)


class TestLimitsService:
    """Backend intelligence for dynamic test limits. UI is display-only."""

    def _to_model(self, row: TestLimitRecord) -> TestLimit:
        direction = (
            LimitDirection(row.direction)
            if row.direction in LimitDirection._value2member_map_
            else LimitDirection.unchanged
        )
        status = (
            LimitStatus(row.status)
            if row.status in LimitStatus._value2member_map_
            else LimitStatus.ACTIVE
        )
        return TestLimit(
            limit_id=row.limit_id,
            parameter=row.parameter,
            test_name=row.test_name,
            site_id=row.site_id,
            tester_id=row.tester_id,
            lot_id=row.lot_id,
            previous_limit=row.previous_limit,
            current_limit=row.current_limit,
            delta=row.delta,
            change_percentage=row.change_percentage,
            direction=direction,
            cpk=row.cpk,
            target_cpk=row.target_cpk,
            confidence=row.confidence,
            reason=row.reason,
            status=status,
            created_at=row.created_at,
            updated_at=row.updated_at,
            change_label=change_label(direction, row.change_percentage),
        )

    async def _audit(
        self,
        db: AsyncSession,
        *,
        limit_id: str,
        action: str,
        actor: str,
        detail: str,
        before_status: str | None,
        after_status: str | None,
        before_limit: float | None,
        after_limit: float | None,
    ) -> LimitAuditRecord:
        row = LimitAuditRecord(
            audit_id=str(uuid4()),
            limit_id=limit_id,
            action=action,
            actor=actor,
            detail=detail,
            before_status=before_status,
            after_status=after_status,
            before_limit=before_limit,
            after_limit=after_limit,
            created_at=datetime.utcnow(),
        )
        db.add(row)
        return row

    async def _bump_adjustments_today(self, db: AsyncSession) -> None:
        state = await db.get(DashboardState, 1)
        if state is None:
            state = DashboardState(id=1)
            db.add(state)
        state.adjustments_today += 1
        state.updated_at = datetime.utcnow()

    async def publish_limit_event(self, row: TestLimitRecord, *, action: str) -> None:
        settings = get_settings()
        model = self._to_model(row)
        event = TelemetryEvent(
            event_id=str(uuid4()),
            event_type=EventType.dynamic_limit_updated,
            timestamp=row.updated_at,
            source="test_limits",
            tester_id=row.tester_id,
            site_id=row.site_id,
            lot_id=row.lot_id,
            wafer_id=None,
            die_id=None,
            sequence_number=int(row.updated_at.timestamp()),
            payload={
                "limit_id": row.limit_id,
                "parameter": row.parameter,
                "test_name": row.test_name,
                "previous_limit": row.previous_limit,
                "current_limit": row.current_limit,
                "delta": row.delta,
                "change_pct": row.change_percentage,
                "change_percentage": row.change_percentage,
                "direction": row.direction,
                "cpk": row.cpk,
                "target_cpk": row.target_cpk,
                "confidence": row.confidence,
                "reason": row.reason,
                "status": row.status,
                "change_label": model.change_label,
                "action": action,
            },
        )
        await publish_event(
            settings.telemetry_channel,
            json.dumps({"kind": "telemetry_event", "event": json.loads(event.model_dump_json())}),
        )

    async def list_limits(self, db: AsyncSession) -> TestLimitsListOut:
        state = await db.get(DashboardState, 1)
        rows = (
            await db.execute(select(TestLimitRecord).order_by(desc(TestLimitRecord.updated_at)).limit(50))
        ).scalars().all()
        return TestLimitsListOut(
            adjustments_today=state.adjustments_today if state else 0,
            items=[self._to_model(r) for r in rows],
        )

    async def get_limit(self, db: AsyncSession, limit_id: str) -> TestLimitDetailOut:
        row = await db.get(TestLimitRecord, limit_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Limit not found")

        adj_rows = (
            await db.execute(
                select(LimitAdjustmentRecord)
                .where(LimitAdjustmentRecord.limit_id == limit_id)
                .order_by(desc(LimitAdjustmentRecord.created_at))
                .limit(50)
            )
        ).scalars().all()
        appr_rows = (
            await db.execute(
                select(LimitApprovalRecord)
                .where(LimitApprovalRecord.limit_id == limit_id)
                .order_by(desc(LimitApprovalRecord.decided_at))
                .limit(50)
            )
        ).scalars().all()
        audit_rows = (
            await db.execute(
                select(LimitAuditRecord)
                .where(LimitAuditRecord.limit_id == limit_id)
                .order_by(desc(LimitAuditRecord.created_at))
                .limit(100)
            )
        ).scalars().all()

        base = self._to_model(row)
        return TestLimitDetailOut(
            **base.model_dump(),
            adjustments=[
                LimitAdjustment(
                    adjustment_id=a.adjustment_id,
                    limit_id=a.limit_id,
                    previous_limit=a.previous_limit,
                    proposed_limit=a.proposed_limit,
                    delta=a.delta,
                    change_percentage=a.change_percentage,
                    direction=LimitDirection(a.direction)
                    if a.direction in LimitDirection._value2member_map_
                    else LimitDirection.unchanged,
                    cpk=a.cpk,
                    target_cpk=a.target_cpk,
                    confidence=a.confidence,
                    reason=a.reason,
                    status=LimitStatus(a.status)
                    if a.status in LimitStatus._value2member_map_
                    else LimitStatus.RECOMMENDED,
                    created_at=a.created_at,
                    created_by=a.created_by,
                )
                for a in adj_rows
            ],
            approvals=[
                LimitApproval(
                    approval_id=p.approval_id,
                    limit_id=p.limit_id,
                    adjustment_id=p.adjustment_id,
                    decision=p.decision,  # type: ignore[arg-type]
                    decided_by=p.decided_by,
                    comment=p.comment,
                    decided_at=p.decided_at,
                )
                for p in appr_rows
            ],
            audits=[
                LimitAudit(
                    audit_id=u.audit_id,
                    limit_id=u.limit_id,
                    action=u.action,
                    actor=u.actor,
                    detail=u.detail,
                    before_status=u.before_status,
                    after_status=u.after_status,
                    before_limit=u.before_limit,
                    after_limit=u.after_limit,
                    created_at=u.created_at,
                )
                for u in audit_rows
            ],
        )

    def calculate_limit_adjustment(self, **kwargs):
        from app.services.test_limits.engine import calculate_limit_adjustment

        return calculate_limit_adjustment(**kwargs)

    def validate_limit_change(self, **kwargs):
        return validate_limit_change(**kwargs)

    def calculate_cpk(self, **kwargs):
        from app.services.test_limits.engine import calculate_cpk

        return calculate_cpk(**kwargs)

    def generate_limit_recommendation(self, **kwargs):
        return generate_limit_recommendation(**kwargs)

    def require_approval(self, **kwargs):
        from app.services.test_limits.engine import require_approval

        return require_approval(**kwargs)

    async def recommend(
        self, db: AsyncSession, limit_id: str, body: RecommendRequest
    ) -> TestLimitDetailOut:
        row = await db.get(TestLimitRecord, limit_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Limit not found")
        if row.status == LimitStatus.PENDING_APPROVAL.value:
            raise HTTPException(status_code=409, detail="Limit already pending approval")

        values = body.samples if body.samples is not None else list(row.sample_values or [])
        if len(values) < 5:
            raise HTTPException(status_code=400, detail="At least 5 samples required for recommendation")

        lsl = body.lsl if body.lsl is not None else row.lsl
        usl = body.usl if body.usl is not None else row.usl
        target = body.target_cpk if body.target_cpk is not None else row.target_cpk

        # Recommend relative to currently active limit
        baseline = row.current_limit
        proposal = generate_limit_recommendation(
            previous_limit=baseline,
            values=values,
            lsl=lsl,
            usl=usl,
            target_cpk=target,
            is_upper_limit=row.is_upper_limit,
        )
        ok, msg = validate_limit_change(
            previous_limit=baseline,
            proposed_limit=proposal.current_limit,
        )
        if not ok:
            raise HTTPException(status_code=400, detail=msg)

        before_status = row.status
        before_limit = row.current_limit
        now = datetime.utcnow()

        adj = LimitAdjustmentRecord(
            adjustment_id=str(uuid4()),
            limit_id=limit_id,
            previous_limit=proposal.previous_limit,
            proposed_limit=proposal.current_limit,
            delta=proposal.delta,
            change_percentage=proposal.change_percentage,
            direction=proposal.direction.value,
            cpk=proposal.cpk,
            target_cpk=proposal.target_cpk,
            confidence=proposal.confidence,
            reason=proposal.reason,
            status=LimitStatus.RECOMMENDED.value,
            created_by=body.actor,
            created_at=now,
        )
        db.add(adj)

        row.previous_limit = proposal.previous_limit
        row.current_limit = proposal.current_limit
        row.delta = proposal.delta
        row.change_percentage = proposal.change_percentage
        row.direction = proposal.direction.value
        row.cpk = proposal.cpk
        row.target_cpk = proposal.target_cpk
        row.confidence = proposal.confidence
        row.reason = proposal.reason
        row.sample_values = values
        if lsl is not None:
            row.lsl = lsl
        if usl is not None:
            row.usl = usl
        row.active_adjustment_id = adj.adjustment_id
        row.updated_at = now

        if proposal.requires_approval:
            row.status = LimitStatus.PENDING_APPROVAL.value
            adj.status = LimitStatus.PENDING_APPROVAL.value
            after_status = LimitStatus.PENDING_APPROVAL.value
            action = "recommend_pending_approval"
        else:
            # Auto-activate small safe tightenings
            row.status = LimitStatus.ACTIVE.value
            adj.status = LimitStatus.ACTIVE.value
            after_status = LimitStatus.ACTIVE.value
            action = "recommend_auto_activated"
            await self._bump_adjustments_today(db)

        await self._audit(
            db,
            limit_id=limit_id,
            action=action,
            actor=body.actor,
            detail=proposal.reason,
            before_status=before_status,
            after_status=after_status,
            before_limit=before_limit,
            after_limit=row.current_limit,
        )
        await db.commit()
        await db.refresh(row)

        if after_status == LimitStatus.ACTIVE.value:
            await self.publish_limit_event(row, action=action)

        return await self.get_limit(db, limit_id)

    async def approve_limit(
        self, db: AsyncSession, limit_id: str, body: ApprovalRequest
    ) -> TestLimitDetailOut:
        row = await db.get(TestLimitRecord, limit_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Limit not found")
        if row.status not in {
            LimitStatus.PENDING_APPROVAL.value,
            LimitStatus.RECOMMENDED.value,
        }:
            raise HTTPException(status_code=409, detail=f"Cannot approve from status {row.status}")

        before_status = row.status
        before_limit = row.previous_limit  # value prior to pending proposal
        now = datetime.utcnow()
        adj_id = row.active_adjustment_id
        if adj_id:
            adj = await db.get(LimitAdjustmentRecord, adj_id)
            if adj:
                adj.status = LimitStatus.ACTIVE.value

        row.status = LimitStatus.ACTIVE.value
        row.updated_at = now
        row.reason = (row.reason or "") + (f" Approved: {body.comment}" if body.comment else " Approved.")

        db.add(
            LimitApprovalRecord(
                approval_id=str(uuid4()),
                limit_id=limit_id,
                adjustment_id=adj_id or "",
                decision="approved",
                decided_by=body.actor,
                comment=body.comment,
                decided_at=now,
            )
        )
        await self._audit(
            db,
            limit_id=limit_id,
            action="approve",
            actor=body.actor,
            detail=body.comment or "approved",
            before_status=before_status,
            after_status=LimitStatus.ACTIVE.value,
            before_limit=before_limit,
            after_limit=row.current_limit,
        )
        await self._bump_adjustments_today(db)
        await db.commit()
        await db.refresh(row)
        await self.publish_limit_event(row, action="approve")
        return await self.get_limit(db, limit_id)

    async def reject_limit(
        self, db: AsyncSession, limit_id: str, body: RejectRequest
    ) -> TestLimitDetailOut:
        row = await db.get(TestLimitRecord, limit_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Limit not found")
        if row.status not in {
            LimitStatus.PENDING_APPROVAL.value,
            LimitStatus.RECOMMENDED.value,
        }:
            raise HTTPException(status_code=409, detail=f"Cannot reject from status {row.status}")

        before_status = row.status
        proposed = row.current_limit
        now = datetime.utcnow()
        adj_id = row.active_adjustment_id
        if adj_id:
            adj = await db.get(LimitAdjustmentRecord, adj_id)
            if adj:
                adj.status = LimitStatus.REJECTED.value

        # Restore previous active limit
        row.current_limit = row.previous_limit
        row.delta = 0.0
        row.change_percentage = 0.0
        row.direction = LimitDirection.unchanged.value
        row.status = LimitStatus.REJECTED.value
        row.updated_at = now
        row.reason = body.comment or "Rejected by engineer"

        db.add(
            LimitApprovalRecord(
                approval_id=str(uuid4()),
                limit_id=limit_id,
                adjustment_id=adj_id or "",
                decision="rejected",
                decided_by=body.actor,
                comment=body.comment,
                decided_at=now,
            )
        )
        await self._audit(
            db,
            limit_id=limit_id,
            action="reject",
            actor=body.actor,
            detail=body.comment or "rejected",
            before_status=before_status,
            after_status=LimitStatus.REJECTED.value,
            before_limit=proposed,
            after_limit=row.current_limit,
        )
        await db.commit()
        await db.refresh(row)
        return await self.get_limit(db, limit_id)

    async def rollback_limit(
        self, db: AsyncSession, limit_id: str, body: RollbackRequest
    ) -> TestLimitDetailOut:
        row = await db.get(TestLimitRecord, limit_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Limit not found")
        if row.status not in {LimitStatus.ACTIVE.value, LimitStatus.REJECTED.value}:
            raise HTTPException(status_code=409, detail=f"Cannot rollback from status {row.status}")

        before_status = row.status
        before_limit = row.current_limit
        now = datetime.utcnow()

        # Roll back to previous_limit snapshot
        restored = row.previous_limit
        row.current_limit = restored
        row.delta = 0.0
        row.change_percentage = 0.0
        row.direction = LimitDirection.unchanged.value
        row.status = LimitStatus.ROLLED_BACK.value
        row.updated_at = now
        row.reason = body.comment or "Rolled back to previous limit"

        if row.active_adjustment_id:
            adj = await db.get(LimitAdjustmentRecord, row.active_adjustment_id)
            if adj:
                adj.status = LimitStatus.ROLLED_BACK.value

        await self._audit(
            db,
            limit_id=limit_id,
            action="rollback",
            actor=body.actor,
            detail=body.comment or "rollback",
            before_status=before_status,
            after_status=LimitStatus.ROLLED_BACK.value,
            before_limit=before_limit,
            after_limit=restored,
        )
        await db.commit()
        await db.refresh(row)
        await self.publish_limit_event(row, action="rollback")
        return await self.get_limit(db, limit_id)
