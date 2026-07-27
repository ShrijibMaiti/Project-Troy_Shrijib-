"""
INTEGRATION #2 — Vendor onboarding profile.

Fixes a documented capture failure: bare-name news searches return nothing
useful for vendors called Plaid, Stripe or Apple. Nobody hand-types "not the
fabric", which is exactly why capture returns zero for those names.

Gemma proposes; the analyst confirms. The draft is never written directly —
it pre-fills the Add Vendor form and the existing POST /vendors does the write.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from backend.ai_assist import gemma
from backend.ai_assist.schemas import VendorProfileDraft

SYSTEM_PROMPT = """\
You are helping configure vendor monitoring. Given a company name, return
identifying details and — most importantly — DISAMBIGUATION TERMS.

The monitoring system searches news for this company by name. Common-word
company names produce false positives: "Plaid" returns fabric articles,
"Stripe" returns clothing, "Apple" returns fruit.

For "negative_terms", list words that appear in articles about the WRONG
subject sharing this name. For "disambiguation_query", write a boolean search
string combining the name with industry terms and excluding the negative terms.

If you do not recognise the company, set entity_type "unknown", leave factual
fields null, still provide plausible negative_terms derived from the name
itself, and set _confidence below 0.4.

Never invent a ticker, LEI or domain. Return ONLY valid JSON.
"""

USER_TEMPLATE = """\
Company name: {name}

Return JSON with exactly these keys:

{{
  "legal_name": string|null,
  "display_name": string|null,
  "entity_type": "public_us"|"public_eu"|"private"|"subsidiary"|"government"|"unknown",
  "primary_domain": string|null,
  "hq_country": "ISO 3166-1 alpha-2"|null,
  "ticker": string|null,
  "aliases": [string],
  "negative_terms": [string],
  "disambiguation_query": string|null,
  "industry": string|null,
  "_confidence": 0.0-1.0,
  "_note": string|null
}}
"""


class ProfileUnavailable(Exception):
    """Gemma not configured or unreachable. Caller returns 503."""


async def profile_vendor(
    session: AsyncSession, *, name: str, org_id: uuid.UUID | None = None
) -> VendorProfileDraft:
    if not gemma.is_configured():
        raise ProfileUnavailable("GEMMA_API_KEY is not configured")

    clean = name.strip()
    if not clean or len(clean) > 200:
        raise ValueError("Vendor name must be 1-200 characters")

    raw = await gemma.generate_json(
        SYSTEM_PROMPT,
        USER_TEMPLATE.format(name=clean),
        model=gemma.model_for("large"),  # needs world knowledge about real companies
        temperature=0.2,
        max_tokens=4096,  # Gemma 4 thinks unconditionally; thoughts consume this budget
        session=session,
        org_id=org_id,
        operation="vendor_profile",
    )
    if raw is None:
        raise ProfileUnavailable("Gemma returned no usable response")

    valid_types = {
        "public_us",
        "public_eu",
        "private",
        "subsidiary",
        "government",
        "unknown",
    }
    et = str(raw.get("entity_type", "unknown")).lower()

    def as_list(v) -> list[str]:
        if isinstance(v, str):
            v = [v]
        return [str(x).strip() for x in (v or []) if str(x).strip()][:12]

    hq = raw.get("hq_country")
    if isinstance(hq, str):
        hq = hq.strip().upper()[:2] or None

    return VendorProfileDraft(
        legal_name=raw.get("legal_name") or clean,
        display_name=raw.get("display_name") or clean,
        entity_type=et if et in valid_types else "unknown",
        primary_domain=raw.get("primary_domain"),
        hq_country=hq,
        ticker=raw.get("ticker"),
        aliases=as_list(raw.get("aliases")),
        negative_terms=as_list(raw.get("negative_terms")),
        disambiguation_query=raw.get("disambiguation_query"),
        industry=raw.get("industry"),
        confidence=float(raw.get("_confidence") or 0.0),
        note=raw.get("_note"),
    )
