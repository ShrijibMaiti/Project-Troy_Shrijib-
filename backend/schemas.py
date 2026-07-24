"""
API response contracts.

These mirror shared/schemas/*.json. Keep them in lockstep; the frontend's
src/types/api.d.ts is generated from the same shapes.

Design rule visible throughout: score dimensions expose raw_value, baseline
AND z_score as separate fields. Collapsing them into one number is what made
the original engine look like a black box.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Vendors
# ---------------------------------------------------------------------------

class VendorCreate(BaseModel):
    legal_name: str
    display_name: str
    lei: str | None = Field(None, pattern=r"^[A-Z0-9]{20}$")
    entity_type: str = "unknown"
    cik: str | None = None
    ticker: str | None = None
    companies_house_number: str | None = None
    crunchbase_uuid: str | None = None
    primary_domain: str | None = None
    careers_url: str | None = None
    aliases: list[str] = []
    negative_terms: list[str] = []
    is_critical: bool = True


class VendorUpdate(BaseModel):
    display_name: str | None = None
    entity_type: str | None = None
    cik: str | None = None
    ticker: str | None = None
    primary_domain: str | None = None
    careers_url: str | None = None
    aliases: list[str] | None = None
    negative_terms: list[str] | None = None
    is_critical: bool | None = None
    is_active: bool | None = None
    capture_enabled: bool | None = None


class VendorOut(ORMModel):
    id: uuid.UUID
    lei: str | None
    legal_name: str
    display_name: str
    entity_type: str
    cik: str | None
    ticker: str | None
    parent_lei: str | None
    is_active: bool
    is_critical: bool
    capture_enabled: bool
    last_capture_at: datetime | None
    last_capture_ok: bool | None
    created_at: datetime


class VendorFleetItem(VendorOut):
    """Fleet row: vendor + current score + freshness."""
    composite: float | None = None
    delta: float | None = None
    open_alerts: int = 0
    # Drives the amber StalenessChip. We instrument our own staleness because
    # staleness is the problem we sell against.
    stale_days: int | None = None
    is_stale: bool = False


# ---------------------------------------------------------------------------
# Signals
# ---------------------------------------------------------------------------

class SignalOut(ORMModel):
    id: uuid.UUID
    vendor_id: uuid.UUID
    metric: str
    source: str
    event_date: date
    observed_at: datetime
    value: float | None
    summary: str
    payload: dict[str, Any]
    source_url: str
    archive_url: str | None
    validator_verdict: str
    validator_confidence: float | None
    chain_seq: int
    row_hash: str


class SignalTimelineItem(SignalOut):
    is_superseded: bool = False
    correction_reason: str | None = None
    corrected_by: str | None = None
    corrected_at: datetime | None = None
    excerpt_text: str | None = None
    confidence: str | None = None


class DisputeIn(BaseModel):
    reason: Literal[
        "wrong_entity",
        "factually_incorrect",
        "duplicate",
        "stale",
        "misclassified",
        "vendor_disputed",
        "other",
    ]
    note: str | None = None


class DisputeOut(BaseModel):
    correction_id: uuid.UUID
    signal_id: uuid.UUID
    score_before: float | None
    score_after: float | None
    recomputed: bool


# ---------------------------------------------------------------------------
# Scores
# ---------------------------------------------------------------------------

class DimensionOut(ORMModel):
    dimension: str
    raw_value: float | None
    baseline: float | None
    z_score: float | None
    anomaly_ratio: float | None
    contribution: float
    weight_applied: float
    context_conditioned: bool
    confidence: str
    signal_ids: list[Any]


class ScoreOut(ORMModel):
    id: uuid.UUID
    vendor_id: uuid.UUID
    composite: float
    previous_composite: float | None
    delta: float | None
    computed_at: datetime
    weights_version: str
    thresholds_version: str
    engine_version: str
    dimensions: list[DimensionOut] = []


class ScorePoint(BaseModel):
    computed_at: datetime
    composite: float


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------

class AlertOut(ORMModel):
    id: uuid.UUID
    vendor_id: uuid.UUID
    severity: str
    fired_at: datetime
    converged_dimensions: list[Any]
    dimension_count: int
    convergence_score: float
    threshold_value: float
    thresholds_version: str
    headline: str
    notified_at: datetime | None
    acknowledged_at: datetime | None
    acknowledged_by: str | None
    is_open: bool


class ThresholdPreviewOut(BaseModel):
    """
    "This threshold would have fired N times." Makes the alert budget tangible
    instead of theoretical — the fix for alert fatigue is a number you can see
    before you commit to it.
    """
    candidate_threshold: float
    current_threshold: float | None
    would_fire: int
    currently_fires: int
    window_days: int
    per_vendor_per_quarter: float
    within_budget: bool
    budget: float = 1.0


# ---------------------------------------------------------------------------
# Narratives
# ---------------------------------------------------------------------------

class CitationOut(BaseModel):
    index: int
    signal_id: uuid.UUID | None = None
    url: str | None = None
    archive_url: str | None = None
    excerpt: str | None = None
    confidence: str | None = None


class NarrativeOut(ORMModel):
    id: uuid.UUID
    vendor_id: uuid.UUID
    narrative_md: str
    citations: list[Any]
    model_id: str
    prompt_hash: str
    prompt_name: str
    generated_at: datetime
    content_hash: str
    is_fallback: bool
    # TWO numbers, never one.
    citation_resolution_pct: float | None
    distinct_claims: int | None
    distinct_citations: int | None
    unresolved_count: int | None
    entailment_fidelity_pct: float | None
    entailment_sampled: int | None
    entailment_failed: int | None


# ---------------------------------------------------------------------------
# Register / contracts
# ---------------------------------------------------------------------------

class ContractIn(BaseModel):
    contractual_arrangement_ref: str
    provider_lei: str | None = None
    provider_legal_name: str
    provider_country: str | None = None
    function_identifier: str | None = None
    function_name: str | None = None
    ict_service_type: str | None = None
    supports_critical_function: bool = False
    start_date: date | None = None
    end_date: date | None = None
    notice_period_days: int | None = None
    governing_law_country: str | None = None
    annual_cost_eur: int | None = None
    data_location_countries: list[str] = []
    processing_location_countries: list[str] = []
    sensitive_data_involved: bool = False
    subcontractors: list[dict[str, Any]] = []
    substitutability: str | None = None
    exit_plan_exists: bool = False
    exit_plan_last_tested: date | None = None
    reintegration_possible: bool | None = None


class ContractOut(ContractIn, ORMModel):
    id: uuid.UUID
    vendor_id: uuid.UUID
    register_version: int
    last_reviewed_by: str | None
    created_at: datetime


class RegisterRow(BaseModel):
    """The join: static ITS fields + live monitoring signal."""
    vendor: VendorOut
    contract: ContractOut | None
    composite: float | None
    last_capture_at: datetime | None
    open_alerts: int
    completeness_pct: float


# ---------------------------------------------------------------------------
# Trust
# ---------------------------------------------------------------------------

class ChainVerifyOut(BaseModel):
    ok: bool
    checked: int
    head_seq: int
    head_hash: str
    first_break_seq: int | None = None
    first_break_id: str | None = None
    reason: str | None = None
    verified_at: datetime


class AuditMetricsOut(BaseModel):
    """
    Two separate honest numbers. The original conflated marker count with
    claim count and only ever proved narrative→row.
    """
    narrative_resolution_pct: float | None
    distinct_claims: int
    distinct_citations: int
    unresolved_count: int
    extraction_fidelity_pct: float | None
    entailment_sampled: int
    entailment_failed: int
    artifacts_counted: int


class AuditLogOut(ORMModel):
    id: uuid.UUID
    action: str
    actor: str
    actor_email: str | None
    entity_type: str | None
    entity_id: uuid.UUID | None
    detail: dict[str, Any]
    note: str | None
    created_at: datetime


# ---------------------------------------------------------------------------
# Methodology
# ---------------------------------------------------------------------------

class MethodologyOut(BaseModel):
    weights: dict[str, Any] | None
    thresholds: dict[str, Any] | None
    lead_time: dict[str, Any] | None
    calibrated: bool
    limitations: list[str]
    engine_version: str


# ---------------------------------------------------------------------------
# Compare / health / jobs
# ---------------------------------------------------------------------------

class CompareCell(BaseModel):
    vendor_id: uuid.UUID
    dimension: str
    z_score: float | None
    contribution: float | None


class CompareOut(BaseModel):
    vendors: list[VendorOut]
    dimensions: list[str]
    matrix: list[CompareCell]
    trends: dict[str, list[ScorePoint]]


class HealthOut(BaseModel):
    status: Literal["ok", "degraded", "error"]
    environment: str
    database: bool
    redis: bool
    calibration: bool
    warnings: list[str]
    version: str


class VendorFreshness(BaseModel):
    vendor_id: uuid.UUID
    display_name: str
    last_capture_at: datetime | None
    last_capture_ok: bool | None
    stale_days: int | None
    is_stale: bool


class JobOut(BaseModel):
    job_id: str
    status: str
    enqueued_at: datetime | None = None
    detail: dict[str, Any] = {}