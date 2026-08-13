from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class LimitStatus(str, Enum):
    RECOMMENDED = "RECOMMENDED"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    ACTIVE = "ACTIVE"
    REJECTED = "REJECTED"
    ROLLED_BACK = "ROLLED_BACK"


class LimitDirection(str, Enum):
    tightened = "tightened"
    widened = "widened"
    unchanged = "unchanged"


class ProcessSample(BaseModel):
    """Parametric samples used for Cpk / limit recommendation (server-side only)."""

    values: list[float]
    lsl: float | None = None
    usl: float | None = None


class TestLimit(BaseModel):
    limit_id: str
    parameter: str
    test_name: str
    site_id: str | None = None
    tester_id: str | None = None
    lot_id: str | None = None
    previous_limit: float
    current_limit: float
    delta: float
    change_percentage: float
    direction: LimitDirection
    cpk: float | None = None
    target_cpk: float = 1.33
    confidence: float | None = None
    reason: str | None = None
    status: LimitStatus
    created_at: datetime
    updated_at: datetime
    # display helpers used by dashboard
    change_label: str | None = None


class LimitAdjustment(BaseModel):
    adjustment_id: str
    limit_id: str
    previous_limit: float
    proposed_limit: float
    delta: float
    change_percentage: float
    direction: LimitDirection
    cpk: float | None = None
    target_cpk: float
    confidence: float | None = None
    reason: str
    status: LimitStatus
    created_at: datetime
    created_by: str = "system"


class LimitApproval(BaseModel):
    approval_id: str
    limit_id: str
    adjustment_id: str
    decision: Literal["approved", "rejected"]
    decided_by: str
    comment: str | None = None
    decided_at: datetime


class LimitAudit(BaseModel):
    audit_id: str
    limit_id: str
    action: str
    actor: str
    detail: str
    before_status: str | None = None
    after_status: str | None = None
    before_limit: float | None = None
    after_limit: float | None = None
    created_at: datetime


class RecommendRequest(BaseModel):
    samples: list[float] | None = None
    lsl: float | None = None
    usl: float | None = None
    target_cpk: float | None = None
    actor: str = "system"


class ApprovalRequest(BaseModel):
    actor: str = "engineer"
    comment: str | None = None


class RejectRequest(BaseModel):
    actor: str = "engineer"
    comment: str | None = None


class RollbackRequest(BaseModel):
    actor: str = "engineer"
    comment: str | None = None


class TestLimitsListOut(BaseModel):
    adjustments_today: int
    items: list[TestLimit]


class TestLimitDetailOut(TestLimit):
    adjustments: list[LimitAdjustment] = Field(default_factory=list)
    approvals: list[LimitApproval] = Field(default_factory=list)
    audits: list[LimitAudit] = Field(default_factory=list)
