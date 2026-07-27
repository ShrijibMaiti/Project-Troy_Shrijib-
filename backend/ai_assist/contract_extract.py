"""
INTEGRATION #1 — Contract PDF → ITS register fields.

Troy's register is manual entry, and we defended that as "the value is in the
join, not the collection." This gets both, and it is the only integration using
Gemma 4's multimodal capability.

THE DRAFT NEVER TOUCHES THE DATABASE. Extract → return → analyst confirms →
the existing PUT endpoint persists. For a product whose output is an adverse
assessment of a named company, that boundary is not optional.

THE PDF IS NEVER STORED. Extract, return, discard the bytes. Storing customer
contracts creates a data-retention obligation nobody asked for.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from backend.ai_assist import gemma
from backend.ai_assist.schemas import ContractDraft, ContractDraftOut

MAX_PDF_BYTES = 10 * 1024 * 1024

SYSTEM_PROMPT = """\
You are a contract analyst extracting structured fields from an ICT
third-party services agreement, for a DORA Article 28(3) register of
information.

RULES:
1. Extract ONLY what the document states. Never infer, never estimate,
   never fill a plausible default.
2. If a field is absent, return null and list it in "_unfound".
3. For every non-null field, provide the verbatim clause it came from in
   "_evidence" (max 200 characters).
4. Assign a confidence 0.0-1.0 per field in "_confidence". Use below 0.7
   when the clause is ambiguous or requires interpretation.
5. Dates as YYYY-MM-DD. Countries as ISO 3166-1 alpha-2 uppercase.
6. "substitutability" must be one of: not_substitutable, highly_complex,
   medium_complex, easily_substitutable — or null. Base it on stated
   switching costs, exclusivity, or bespoke integration, not on your own
   impression.
7. Return ONLY valid JSON matching the schema. No prose, no markdown fences.

You are drafting for human review. An analyst will verify every field
before it is saved. Under-extraction is safe. Over-extraction is not.
"""

USER_PROMPT = """\
Extract the register fields from the attached agreement.

Return JSON with exactly these keys:

{
  "contractual_arrangement_ref": string|null,
  "provider_legal_name": string|null,
  "provider_lei": string|null,
  "provider_country": string|null,
  "function_identifier": string|null,
  "function_name": string|null,
  "ict_service_type": string|null,
  "supports_critical_function": boolean|null,
  "start_date": "YYYY-MM-DD"|null,
  "end_date": "YYYY-MM-DD"|null,
  "notice_period_days": integer|null,
  "governing_law_country": string|null,
  "annual_cost_eur": integer|null,
  "data_location_countries": [string],
  "processing_location_countries": [string],
  "sensitive_data_involved": boolean|null,
  "subcontractors": [{"name": string, "lei": string|null, "rank": integer, "country": string|null}],
  "substitutability": string|null,
  "exit_plan_exists": boolean|null,
  "exit_plan_last_tested": "YYYY-MM-DD"|null,
  "reintegration_possible": boolean|null,
  "_confidence": {"field_name": 0.0-1.0},
  "_evidence": {"field_name": "verbatim clause, max 200 chars"},
  "_unfound": ["field names not present in the document"]
}
"""


class ExtractionUnavailable(Exception):
    """Gemma is not configured or not reachable. Caller returns 503."""


async def extract_contract(
    session: AsyncSession,
    *,
    vendor_id: uuid.UUID,
    org_id: uuid.UUID,
    pdf_bytes: bytes,
    filename: str = "contract.pdf",
) -> ContractDraftOut:
    if not gemma.is_configured():
        raise ExtractionUnavailable("GEMMA_API_KEY is not configured")

    if len(pdf_bytes) > MAX_PDF_BYTES:
        raise ValueError(f"PDF exceeds {MAX_PDF_BYTES // (1024 * 1024)} MB limit")

    if not pdf_bytes.startswith(b"%PDF"):
        raise ValueError("File does not appear to be a PDF")

    raw = await gemma.generate_json(
        SYSTEM_PROMPT,
        USER_PROMPT,
        model=gemma.model_for("vision"),
        files=[("application/pdf", pdf_bytes)],
        temperature=0.05,  # extraction, not creativity
        max_tokens=12288,
        session=session,
        org_id=org_id,
        vendor_id=vendor_id,
        operation="contract_extract",
    )

    if raw is None:
        raise ExtractionUnavailable("Gemma returned no usable response")

    confidence = raw.pop("_confidence", {}) or {}
    evidence = raw.pop("_evidence", {}) or {}
    unfound = raw.pop("_unfound", []) or []

    draft = ContractDraft(**_coerce(raw))

    return ContractDraftOut(
        draft=draft,
        confidence={k: float(v) for k, v in confidence.items() if _is_num(v)},
        evidence={k: str(v)[:200] for k, v in evidence.items()},
        unfound=[str(u) for u in unfound],
        extracted_at=datetime.now(timezone.utc),
        model_id=gemma.model_for("vision"),
        vendor_id=vendor_id,
    )


def _coerce(raw: dict) -> dict:
    """
    Defensive coercion. A model returning "2025-01-01" as a string, or a
    country as lowercase, should not lose the whole extraction to a
    validation error — the analyst is reviewing this anyway.
    """
    out = dict(raw)

    for f in ("start_date", "end_date", "exit_plan_last_tested"):
        v = out.get(f)
        if isinstance(v, str):
            try:
                out[f] = date.fromisoformat(v[:10])
            except ValueError:
                out[f] = None

    for f in ("provider_country", "governing_law_country"):
        v = out.get(f)
        if isinstance(v, str):
            out[f] = v.strip().upper()[:2] or None

    for f in ("data_location_countries", "processing_location_countries"):
        v = out.get(f)
        if isinstance(v, str):
            v = [v]
        out[f] = [str(x).strip().upper()[:2] for x in (v or []) if x]

    lei = out.get("provider_lei")
    if isinstance(lei, str):
        lei = lei.strip().upper()
        out["provider_lei"] = lei if len(lei) == 20 else None

    subs = out.get("subcontractors")
    if not isinstance(subs, list):
        out["subcontractors"] = []

    v = out.get("substitutability")
    valid = {
        "not_substitutable",
        "highly_complex",
        "medium_complex",
        "easily_substitutable",
    }
    out["substitutability"] = v if v in valid else None

    for f in ("notice_period_days", "annual_cost_eur"):
        v = out.get(f)
        if isinstance(v, str):
            digits = "".join(ch for ch in v if ch.isdigit())
            out[f] = int(digits) if digits else None

    return {k: v for k, v in out.items() if not k.startswith("_")}


def _is_num(v) -> bool:
    try:
        float(v)
        return True
    except (TypeError, ValueError):
        return False
