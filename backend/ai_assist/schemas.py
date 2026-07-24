"""
Draft models — never persisted directly.

Every one of these represents Gemma output awaiting human confirmation. The
naming is deliberate: a "Draft" is not a record. The confirm step goes through
the existing, tested endpoints.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field


class ContractDraft(BaseModel):
    """Mirrors ContractIn — see backend/schemas.py — but everything is optional."""

    contractual_arrangement_ref: str | None = None
    provider_legal_name: str | None = None
    provider_lei: str | None = None
    provider_country: str | None = None
    function_identifier: str | None = None
    function_name: str | None = None
    ict_service_type: str | None = None
    supports_critical_function: bool | None = None
    start_date: date | None = None
    end_date: date | None = None
    notice_period_days: int | None = None
    governing_law_country: str | None = None
    annual_cost_eur: int | None = None
    data_location_countries: list[str] = []
    processing_location_countries: list[str] = []
    sensitive_data_involved: bool | None = None
    subcontractors: list[dict[str, Any]] = []
    substitutability: str | None = None
    exit_plan_exists: bool | None = None
    exit_plan_last_tested: date | None = None
    reintegration_possible: bool | None = None


class ContractDraftOut(BaseModel):
    draft: ContractDraft
    # Per-field, so the analyst knows which values to scrutinise.
    confidence: dict[str, float] = {}
    # The verbatim clause each value came from. NOT OPTIONAL — an extracted
    # value with no source is exactly what this product argues against.
    evidence: dict[str, str] = {}
    unfound: list[str] = []
    extracted_at: datetime
    model_id: str
    vendor_id: uuid.UUID
    note: str = (
        "Draft only. Nothing has been saved. Review every field, then confirm "
        "through PUT /register/contract/{vendor_id}."
    )


class VendorProfileDraft(BaseModel):
    legal_name: str | None = None
    display_name: str | None = None
    entity_type: str = "unknown"
    primary_domain: str | None = None
    hq_country: str | None = None
    ticker: str | None = None
    aliases: list[str] = []
    negative_terms: list[str] = []
    disambiguation_query: str | None = None
    industry: str | None = None
    confidence: float = 0.0
    note: str | None = None


class ExplainOut(BaseModel):
    headline: str
    explanation: str
    # Mandatory. A rising score explained without its limitation is a claim;
    # explained with it, it is analysis.
    caveat: str
    dimension: str
    cached: bool = False