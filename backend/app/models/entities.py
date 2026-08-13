"""
Persistent domain models — PostgreSQL via SQLAlchemy.

Architecture: API → Service → Repository → SQLAlchemy → PostgreSQL
React never queries the database; all dashboard values trace to these rows
or live telemetry projected into them.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.core.database import Base

JSONType = JSON().with_variant(JSONB(), "postgresql")


# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(128), default="")
    password_hash: Mapped[str] = mapped_column(String(256))
    role: Mapped[str] = mapped_column(String(32), default="VIEWER", index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# ---------------------------------------------------------------------------
# Sites & testers
# ---------------------------------------------------------------------------


class TesterSite(Base):
    __tablename__ = "tester_sites"

    site_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    fab: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    testers: Mapped[list[Tester]] = relationship(back_populates="site")


class Tester(Base):
    __tablename__ = "testers"
    __table_args__ = (Index("ix_testers_site_id", "site_id"),)

    tester_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32), default="online")
    site_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("tester_sites.site_id", ondelete="SET NULL"), nullable=True
    )
    health_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    site: Mapped[TesterSite | None] = relationship(back_populates="testers")
    lots: Mapped[list[Lot]] = relationship(back_populates="tester")
    test_runs: Mapped[list[TestRun]] = relationship(back_populates="tester")


# ---------------------------------------------------------------------------
# Lot / wafer / die
# ---------------------------------------------------------------------------


class Lot(Base):
    __tablename__ = "lots"
    __table_args__ = (
        Index("ix_lots_tester_id", "tester_id"),
        Index("ix_lots_site_id", "site_id"),
        Index("ix_lots_started_at", "started_at"),
    )

    lot_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    status: Mapped[str] = mapped_column(String(32), default="active")
    tester_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("testers.tester_id", ondelete="SET NULL"), nullable=True
    )
    site_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("tester_sites.site_id", ondelete="SET NULL"), nullable=True
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    test_time_saved_hours: Mapped[float] = mapped_column(Float, default=0.0)
    overall_yield_pct: Mapped[float] = mapped_column(Float, default=0.0)

    tester: Mapped[Tester | None] = relationship(back_populates="lots")
    wafers: Mapped[list[Wafer]] = relationship(back_populates="lot")
    test_runs: Mapped[list[TestRun]] = relationship(back_populates="lot")


class Wafer(Base):
    __tablename__ = "wafers"
    __table_args__ = (
        Index("ix_wafers_lot_id", "lot_id"),
        Index("ix_wafers_tester_id", "tester_id"),
        Index("ix_wafers_updated_at", "updated_at"),
    )

    wafer_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    lot_id: Mapped[str] = mapped_column(String(64), ForeignKey("lots.lot_id", ondelete="CASCADE"))
    tester_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("testers.tester_id", ondelete="SET NULL"), nullable=True
    )
    site_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("tester_sites.site_id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(32), default="testing")
    yield_pct: Mapped[float] = mapped_column(Float, default=0.0)
    total_dies: Mapped[int] = mapped_column(Integer, default=0)
    tested_dies: Mapped[int] = mapped_column(Integer, default=0)
    pass_count: Mapped[int] = mapped_column(Integer, default=0)
    fail_count: Mapped[int] = mapped_column(Integer, default=0)
    retest_count: Mapped[int] = mapped_column(Integer, default=0)
    reclass_count: Mapped[int] = mapped_column(Integer, default=0)
    caption: Mapped[str] = mapped_column(String(128), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    lot: Mapped[Lot] = relationship(back_populates="wafers")
    dies: Mapped[list[Die]] = relationship(back_populates="wafer")
    metrics: Mapped[list[WaferMetric]] = relationship(back_populates="wafer")


class Die(Base):
    __tablename__ = "dies"
    __table_args__ = (
        UniqueConstraint("wafer_id", "x", "y", name="uq_die_coord"),
        Index("ix_dies_wafer_id", "wafer_id"),
    )

    die_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    wafer_id: Mapped[str] = mapped_column(String(64), ForeignKey("wafers.wafer_id", ondelete="CASCADE"))
    x: Mapped[int] = mapped_column(Integer)  # column
    y: Mapped[int] = mapped_column(Integer)  # row
    bin: Mapped[str] = mapped_column(String(16), default="untested")
    fail_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    test_time_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    wafer: Mapped[Wafer] = relationship(back_populates="dies")
    test_results: Mapped[list[DieTestResult]] = relationship(back_populates="die")


class DieTestResult(Base):
    """Historical per-die test outcomes (append-only)."""

    __tablename__ = "die_test_results"
    __table_args__ = (
        Index("ix_die_test_results_die_id", "die_id"),
        Index("ix_die_test_results_wafer_id", "wafer_id"),
        Index("ix_die_test_results_timestamp", "timestamp"),
        Index("ix_die_test_results_lot_id", "lot_id"),
        Index("ix_die_test_results_tester_id", "tester_id"),
    )

    result_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    die_id: Mapped[str] = mapped_column(String(64), ForeignKey("dies.die_id", ondelete="CASCADE"))
    wafer_id: Mapped[str] = mapped_column(String(64), ForeignKey("wafers.wafer_id", ondelete="CASCADE"))
    lot_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("lots.lot_id", ondelete="SET NULL"), nullable=True
    )
    tester_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("testers.tester_id", ondelete="SET NULL"), nullable=True
    )
    site_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("tester_sites.site_id", ondelete="SET NULL"), nullable=True
    )
    test_run_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("test_runs.run_id", ondelete="SET NULL"), nullable=True
    )
    result: Mapped[str] = mapped_column(String(16), default="untested")
    fail_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    test_time_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)

    die: Mapped[Die] = relationship(back_populates="test_results")


# ---------------------------------------------------------------------------
# Test runs & pattern optimization
# ---------------------------------------------------------------------------


class TestRun(Base):
    __tablename__ = "test_runs"
    __table_args__ = (
        Index("ix_test_runs_lot_id", "lot_id"),
        Index("ix_test_runs_wafer_id", "wafer_id"),
        Index("ix_test_runs_tester_id", "tester_id"),
        Index("ix_test_runs_site_id", "site_id"),
        Index("ix_test_runs_started_at", "started_at"),
    )

    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    lot_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("lots.lot_id", ondelete="SET NULL"), nullable=True
    )
    wafer_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("wafers.wafer_id", ondelete="SET NULL"), nullable=True
    )
    tester_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("testers.tester_id", ondelete="SET NULL"), nullable=True
    )
    site_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("tester_sites.site_id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(32), default="running")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dies_tested: Mapped[int] = mapped_column(Integer, default=0)
    yield_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    lot: Mapped[Lot | None] = relationship(back_populates="test_runs")
    tester: Mapped[Tester | None] = relationship(back_populates="test_runs")


class PatternOptimizationResult(Base):
    __tablename__ = "pattern_optimization_results"
    __table_args__ = (
        Index("ix_pattern_opt_lot_id", "lot_id"),
        Index("ix_pattern_opt_wafer_id", "wafer_id"),
        Index("ix_pattern_opt_tester_id", "tester_id"),
        Index("ix_pattern_opt_created_at", "created_at"),
    )

    result_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    lot_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("lots.lot_id", ondelete="SET NULL"), nullable=True
    )
    wafer_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("wafers.wafer_id", ondelete="SET NULL"), nullable=True
    )
    tester_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("testers.tester_id", ondelete="SET NULL"), nullable=True
    )
    pattern_group: Mapped[str | None] = mapped_column(String(128), nullable=True)
    summary: Mapped[str] = mapped_column(Text, default="")
    footprint_reduction_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    test_time_reduction_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


# ---------------------------------------------------------------------------
# Metrics / KPIs
# ---------------------------------------------------------------------------


class WaferMetric(Base):
    __tablename__ = "wafer_metrics"
    __table_args__ = (
        Index("ix_wafer_metrics_wafer_id", "wafer_id"),
        Index("ix_wafer_metrics_lot_id", "lot_id"),
        Index("ix_wafer_metrics_timestamp", "timestamp"),
        Index("ix_wafer_metrics_metric_key", "metric_key"),
    )

    metric_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    wafer_id: Mapped[str] = mapped_column(String(64), ForeignKey("wafers.wafer_id", ondelete="CASCADE"))
    lot_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("lots.lot_id", ondelete="SET NULL"), nullable=True
    )
    metric_key: Mapped[str] = mapped_column(String(64))
    value: Mapped[float] = mapped_column(Float, default=0.0)
    unit: Mapped[str] = mapped_column(String(16), default="%")
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    wafer: Mapped[Wafer] = relationship(back_populates="metrics")


class OptimizationMetric(Base):
    """Current KPI snapshot (dashboard optimization cards)."""

    __tablename__ = "optimization_metrics"

    # `key` retained for API/KPI compatibility; also exposed as metric_id
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(128))
    value: Mapped[float] = mapped_column(Float, default=0.0)
    unit: Mapped[str] = mapped_column(String(16), default="%")
    baseline: Mapped[float] = mapped_column(Float, default=0.0)
    target: Mapped[float] = mapped_column(Float, default=0.0)
    previous_value: Mapped[float] = mapped_column(Float, default=0.0)
    improvement: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(32), default="on_track")
    description: Mapped[str] = mapped_column(Text, default="")
    accent: Mapped[str] = mapped_column(String(32), default="#6EE7A8")
    trend: Mapped[str] = mapped_column(String(8), default="up")
    series: Mapped[list[Any]] = mapped_column(JSONType, default=list)
    history: Mapped[list[Any]] = mapped_column(JSONType, default=list)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, index=True)

    history_rows: Mapped[list[OptimizationMetricHistory]] = relationship(back_populates="metric")

    @property
    def metric_id(self) -> str:
        return self.key


class OptimizationMetricHistory(Base):
    __tablename__ = "optimization_metric_history"
    __table_args__ = (
        Index("ix_opt_metric_hist_metric_id", "metric_id"),
        Index("ix_opt_metric_hist_timestamp", "timestamp"),
    )

    history_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    metric_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("optimization_metrics.key", ondelete="CASCADE")
    )
    value: Mapped[float] = mapped_column(Float)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    source: Mapped[str] = mapped_column(String(64), default="system")
    meta: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)

    metric: Mapped[OptimizationMetric] = relationship(back_populates="history_rows")


# ---------------------------------------------------------------------------
# Predictive maintenance & dynamic limits
# ---------------------------------------------------------------------------


class PredictiveMaintenance(Base):
    __tablename__ = "predictive_maintenance"
    __table_args__ = (
        Index("ix_pm_tester_id", "tester_id"),
        Index("ix_pm_severity", "severity"),
        Index("ix_pm_updated_at", "updated_at"),
    )

    asset_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tester_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("testers.tester_id", ondelete="SET NULL"), nullable=True
    )
    site_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("tester_sites.site_id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(128))
    component: Mapped[str | None] = mapped_column(String(128), nullable=True)
    health_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="ok")
    rul_days: Mapped[float | None] = mapped_column(Float, nullable=True)
    failure_probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    severity: Mapped[str] = mapped_column(String(32), default="unavailable")
    recommended_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_available: Mapped[bool] = mapped_column(Boolean, default=True)
    features: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class DynamicTestLimit(Base):
    __tablename__ = "dynamic_test_limits"
    __table_args__ = (
        Index("ix_dtl_site_id", "site_id"),
        Index("ix_dtl_tester_id", "tester_id"),
        Index("ix_dtl_lot_id", "lot_id"),
        Index("ix_dtl_status", "status"),
        Index("ix_dtl_updated_at", "updated_at"),
    )

    limit_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    parameter: Mapped[str] = mapped_column(String(128))
    test_name: Mapped[str] = mapped_column(String(128))
    site_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("tester_sites.site_id", ondelete="SET NULL"), nullable=True
    )
    tester_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("testers.tester_id", ondelete="SET NULL"), nullable=True
    )
    lot_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("lots.lot_id", ondelete="SET NULL"), nullable=True
    )
    previous_limit: Mapped[float] = mapped_column(Float, default=0.0)
    current_limit: Mapped[float] = mapped_column(Float, default=0.0)
    delta: Mapped[float] = mapped_column(Float, default=0.0)
    change_percentage: Mapped[float] = mapped_column(Float, default=0.0)
    direction: Mapped[str] = mapped_column(String(16), default="unchanged")
    cpk: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_cpk: Mapped[float] = mapped_column(Float, default=1.33)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE")
    is_upper_limit: Mapped[bool] = mapped_column(Boolean, default=True)
    lsl: Mapped[float | None] = mapped_column(Float, nullable=True)
    usl: Mapped[float | None] = mapped_column(Float, nullable=True)
    sample_values: Mapped[list[Any] | None] = mapped_column(JSONType, nullable=True)
    active_adjustment_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class LimitAdjustmentRecord(Base):
    __tablename__ = "limit_adjustments"
    __table_args__ = (Index("ix_limit_adj_limit_id", "limit_id"), Index("ix_limit_adj_created_at", "created_at"))

    adjustment_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    limit_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("dynamic_test_limits.limit_id", ondelete="CASCADE")
    )
    previous_limit: Mapped[float] = mapped_column(Float)
    proposed_limit: Mapped[float] = mapped_column(Float)
    delta: Mapped[float] = mapped_column(Float)
    change_percentage: Mapped[float] = mapped_column(Float)
    direction: Mapped[str] = mapped_column(String(16))
    cpk: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_cpk: Mapped[float] = mapped_column(Float, default=1.33)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    reason: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), index=True)
    created_by: Mapped[str] = mapped_column(String(128), default="system")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class LimitApprovalRecord(Base):
    __tablename__ = "limit_approvals"

    approval_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    limit_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("dynamic_test_limits.limit_id", ondelete="CASCADE"), index=True
    )
    adjustment_id: Mapped[str] = mapped_column(String(64), index=True)
    decision: Mapped[str] = mapped_column(String(16))
    decided_by: Mapped[str] = mapped_column(String(128))
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, index=True)


class LimitAuditRecord(Base):
    __tablename__ = "limit_audits"

    audit_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    limit_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("dynamic_test_limits.limit_id", ondelete="CASCADE"), index=True
    )
    action: Mapped[str] = mapped_column(String(64))
    actor: Mapped[str] = mapped_column(String(128))
    detail: Mapped[str] = mapped_column(Text, default="")
    before_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    after_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    before_limit: Mapped[float | None] = mapped_column(Float, nullable=True)
    after_limit: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, index=True)


# ---------------------------------------------------------------------------
# Events, alerts, audit
# ---------------------------------------------------------------------------


class TelemetryEvent(Base):
    """
    Raw ingested telemetry bus events (append-only).

    Dimensional ids are indexed soft references so the bus can accept events
    before domain rows exist; projections then create Lot/Wafer/Die/Tester
    with proper foreign keys.
    """

    __tablename__ = "telemetry_events"
    __table_args__ = (
        Index("ix_telemetry_events_timestamp", "timestamp"),
        Index("ix_telemetry_events_event_type", "event_type"),
        Index("ix_telemetry_events_wafer_id", "wafer_id"),
        Index("ix_telemetry_events_lot_id", "lot_id"),
        Index("ix_telemetry_events_tester_id", "tester_id"),
        Index("ix_telemetry_events_site_id", "site_id"),
        Index("ix_telemetry_events_die_id", "die_id"),
        Index("ix_telemetry_events_sequence_number", "sequence_number"),
    )

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(64))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    source: Mapped[str] = mapped_column(String(64))
    tester_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    site_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    lot_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    wafer_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    die_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sequence_number: Mapped[int] = mapped_column(Integer)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    log_tag: Mapped[str] = mapped_column(String(16), default="info")
    log_text: Mapped[str] = mapped_column(Text, default="")


class TestEvent(Base):
    """Materialized floor event-center rows (ops UI)."""

    __tablename__ = "test_events"
    __table_args__ = (
        Index("ix_test_events_timestamp", "timestamp"),
        Index("ix_test_events_event_type", "event_type"),
        Index("ix_test_events_severity", "severity"),
        Index("ix_test_events_wafer_id", "wafer_id"),
        Index("ix_test_events_lot_id", "lot_id"),
        Index("ix_test_events_tester_id", "tester_id"),
        Index("ix_test_events_site_id", "site_id"),
        Index("ix_test_events_sequence_number", "sequence_number"),
        Index("ix_test_events_acknowledged", "acknowledged"),
    )

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(64))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    severity: Mapped[str] = mapped_column(String(16), default="INFO")
    source: Mapped[str] = mapped_column(String(64), default="ingestion")
    tester_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("testers.tester_id", ondelete="SET NULL"), nullable=True
    )
    site_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("tester_sites.site_id", ondelete="SET NULL"), nullable=True
    )
    lot_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("lots.lot_id", ondelete="SET NULL"), nullable=True
    )
    wafer_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("wafers.wafer_id", ondelete="SET NULL"), nullable=True
    )
    die_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    message: Mapped[str] = mapped_column(Text, default="")
    event_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSONType, default=dict)
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)
    acknowledged_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sequence_number: Mapped[int] = mapped_column(Integer, default=0)
    tag: Mapped[str] = mapped_column(String(16), default="info")
    text: Mapped[str] = mapped_column(Text, default="")


class Alert(Base):
    __tablename__ = "alerts"
    __table_args__ = (
        Index("ix_alerts_timestamp", "timestamp"),
        Index("ix_alerts_severity", "severity"),
        Index("ix_alerts_tester_id", "tester_id"),
        Index("ix_alerts_lot_id", "lot_id"),
        Index("ix_alerts_wafer_id", "wafer_id"),
        Index("ix_alerts_site_id", "site_id"),
        Index("ix_alerts_status", "status"),
    )

    alert_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    severity: Mapped[str] = mapped_column(String(16), default="WARN")
    alert_type: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(256))
    message: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="open")
    tester_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("testers.tester_id", ondelete="SET NULL"), nullable=True
    )
    site_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("tester_sites.site_id", ondelete="SET NULL"), nullable=True
    )
    lot_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("lots.lot_id", ondelete="SET NULL"), nullable=True
    )
    wafer_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("wafers.wafer_id", ondelete="SET NULL"), nullable=True
    )
    source_event_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)
    acknowledged_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_timestamp", "timestamp"),
        Index("ix_audit_logs_entity_type", "entity_type"),
        Index("ix_audit_logs_entity_id", "entity_id"),
        Index("ix_audit_logs_actor", "actor"),
    )

    audit_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    actor: Mapped[str] = mapped_column(String(128))
    action: Mapped[str] = mapped_column(String(64))
    entity_type: Mapped[str] = mapped_column(String(64))
    entity_id: Mapped[str] = mapped_column(String(64))
    detail: Mapped[str] = mapped_column(Text, default="")
    before_json: Mapped[dict[str, Any] | None] = mapped_column(JSONType, nullable=True)
    after_json: Mapped[dict[str, Any] | None] = mapped_column(JSONType, nullable=True)
    tester_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    lot_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    wafer_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    site_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)


# ---------------------------------------------------------------------------
# Supporting / projection tables (kept for dashboard header + PM history)
# ---------------------------------------------------------------------------


class TelemetryFeatureRow(Base):
    __tablename__ = "telemetry_features"
    __table_args__ = (
        Index("ix_telemetry_features_tester_id", "tester_id"),
        Index("ix_telemetry_features_captured_at", "captured_at"),
    )

    feature_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tester_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("testers.tester_id", ondelete="CASCADE")
    )
    component: Mapped[str] = mapped_column(String(128))
    test_failures: Mapped[float] = mapped_column(Float, default=0.0)
    parametric_drift: Mapped[float] = mapped_column(Float, default=0.0)
    contact_resistance: Mapped[float] = mapped_column(Float, default=0.0)
    temperature: Mapped[float] = mapped_column(Float, default=0.0)
    voltage_deviation: Mapped[float] = mapped_column(Float, default=0.0)
    current_deviation: Mapped[float] = mapped_column(Float, default=0.0)
    cycle_count: Mapped[float] = mapped_column(Float, default=0.0)
    historical_failures: Mapped[float] = mapped_column(Float, default=0.0)
    maintenance_events: Mapped[float] = mapped_column(Float, default=0.0)
    tester_utilization: Mapped[float] = mapped_column(Float, default=0.0)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class MaintenancePredictionRow(Base):
    __tablename__ = "maintenance_predictions"
    __table_args__ = (
        Index("ix_maint_pred_tester_id", "tester_id"),
        Index("ix_maint_pred_created_at", "created_at"),
        Index("ix_maint_pred_severity", "severity"),
    )

    prediction_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tester_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("testers.tester_id", ondelete="CASCADE")
    )
    component: Mapped[str] = mapped_column(String(128))
    health_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    failure_probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    rul_days: Mapped[float | None] = mapped_column(Float, nullable=True)
    severity: Mapped[str] = mapped_column(String(32))
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    recommended_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommendation_json: Mapped[dict[str, Any] | None] = mapped_column(JSONType, nullable=True)
    model_available: Mapped[bool] = mapped_column(Boolean, default=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    features_json: Mapped[dict[str, Any] | None] = mapped_column(JSONType, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class MaintenanceHistory(Base):
    __tablename__ = "maintenance_history"
    __table_args__ = (
        Index("ix_maint_hist_tester_id", "tester_id"),
        Index("ix_maint_hist_created_at", "created_at"),
    )

    history_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tester_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("testers.tester_id", ondelete="CASCADE")
    )
    component: Mapped[str] = mapped_column(String(128))
    event_type: Mapped[str] = mapped_column(String(64))
    detail: Mapped[str] = mapped_column(Text, default="")
    health_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    severity: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class DashboardState(Base):
    __tablename__ = "dashboard_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    lots_in_test: Mapped[int] = mapped_column(Integer, default=0)
    test_time_saved_hours: Mapped[float] = mapped_column(Float, default=0.0)
    overall_yield_pct: Mapped[float] = mapped_column(Float, default=0.0)
    active_wafer_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("wafers.wafer_id", ondelete="SET NULL"), nullable=True
    )
    adjustments_today: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


# ---------------------------------------------------------------------------
# Backward-compatible aliases (existing services keep importing these names)
# ---------------------------------------------------------------------------

TelemetryEventRow = TelemetryEvent
FloorEventView = TestEvent
TestLimitRecord = DynamicTestLimit
TestLimitAdjustment = DynamicTestLimit
KpiMetric = OptimizationMetric
MaintenanceAsset = PredictiveMaintenance
