"""
Ingestion adapter: Wrik's pipeline output -> Troy's chained evidence + scores.

His output shape is FIXED. This module is the one-directional translation
layer that conforms it to Troy's models. Nothing here reaches back into his
pipeline; it only reads his output dict.

Two rules that are load-bearing:

  1. Evidence enters through append_signal(), never a raw insert. If his
     signals bypassed the hash chain, Troy's tamper-evidence claim would not
     cover his data — which is the whole product.

  2. We NEVER fabricate a baseline or z-score. His pipeline does not emit
     them, so we store raw_value and leave baseline/z_score NULL, flagged.
     A made-up baseline is the black-box behaviour this system exists to
     refuse.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.integrity.hash_chain import append_signal
from db.models.score import DimensionScore, VendorScore
from db.models.signal import Signal, SignalMetric, SignalSource
from db.models.vendor import EntityType, Vendor

# His dimension keys -> Troy's SignalMetric. Anything not here is not scored.
DIMENSION_MAP = {
    "news_volume_risk": SignalMetric.NEWS_VOLUME,
    "legal_risk": SignalMetric.LEGAL_EVENT,
    "headcount_risk": SignalMetric.HEADCOUNT_CHANGE,
}

# His free-text source label -> Troy's SignalSource. Falls back to MANUAL.
SOURCE_MAP = {
    "gdelt": SignalSource.GDELT,
    "courtlistener": SignalSource.COURTLISTENER,
    "sec": SignalSource.SEC_EDGAR,
    "sec_edgar": SignalSource.SEC_EDGAR,
    "companies_house": SignalSource.COMPANIES_HOUSE,
    "crunchbase": SignalSource.CRUNCHBASE,
    "brightdata": SignalSource.BRIGHTDATA_MCP,
}

# Marks a dimension whose baseline/z-score the upstream engine did not provide.
NO_BASELINE_NOTE = "baseline_not_provided_by_engine"

PROVISIONAL_WEIGHTS_VERSION = "pipeline-v0-unversioned"
PROVISIONAL_THRESHOLDS_VERSION = "pipeline-v0-unversioned"
ENGINE_VERSION = "wrik-pipeline-0.1"


def _source(label: str | None) -> SignalSource:
    if not label:
        return SignalSource.MANUAL
    return SOURCE_MAP.get(label.strip().lower(), SignalSource.MANUAL)


def _metric_for_evidence(dimensions: dict) -> SignalMetric:
    """
    His evidence_trail items are not tagged by dimension. Attribute each to
    the dimension carrying the most weight, so a legal-heavy vendor's sources
    are filed as legal events. Defensible, and honest about being approximate.
    """
    if not dimensions:
        return SignalMetric.NEWS_VOLUME
    top = max(dimensions.items(), key=lambda kv: kv[1] or 0)[0]
    return DIMENSION_MAP.get(top, SignalMetric.NEWS_VOLUME)


def _dedup_key(vendor_id: uuid.UUID, url: str, d: date, metric: str) -> str:
    return hashlib.sha256(
        f"{vendor_id}|{url}|{d.isoformat()}|{metric}".encode()
    ).hexdigest()


async def ingest_pipeline_output(
    session: AsyncSession,
    org_id: uuid.UUID,
    output: dict,
) -> dict:
    """
    Ingest ONE vendor result in Wrik's output shape:

      {
        "vendor_name": str,
        "composite_risk_score": float (0-10),
        "risk_posture": "LOW"|"ELEVATED"|"HIGH",
        "dimensions": {"news_volume_risk": float, "legal_risk": float, "headcount_risk": float},
        "evidence_trail": [{"source": str, "title": str, "url": str}]
      }

    Returns a small summary dict. Caller commits.
    """
    name = output["vendor_name"]
    now = datetime.now(timezone.utc)
    today = now.date()

    # --- Vendor (find or create) -----------------------------------------
    vendor = (
        await session.execute(
            select(Vendor).where(Vendor.org_id == org_id, Vendor.display_name == name)
        )
    ).scalar_one_or_none()

    if vendor is None:
        vendor = Vendor(
            legal_name=name,
            display_name=name,
            entity_type=EntityType.UNKNOWN,
            org_id=org_id,
            capture_enabled=False,  # this data comes from the pipeline, not capture
        )
        session.add(vendor)
        await session.flush()

    dimensions: dict[str, float] = output.get("dimensions", {}) or {}

    # --- Evidence -> hash-chained Signals --------------------------------
    metric = _metric_for_evidence(dimensions)
    written = 0
    for item in output.get("evidence_trail", []) or []:
        url = item.get("url") or f"pipeline://{vendor.id}/{written}"
        title = item.get("title") or "(untitled source)"
        dedup = _dedup_key(vendor.id, url, today, metric.value)

        exists = (
            await session.execute(select(Signal.id).where(Signal.dedup_key == dedup))
        ).scalar_one_or_none()
        if exists:
            continue

        sig = Signal(
            vendor_id=vendor.id,
            metric=metric,
            source=_source(item.get("source")),
            event_date=today,
            observed_at=now,
            value=None,
            summary=title[:2000],
            payload={"ingested_from": "pipeline", "raw_source": item.get("source")},
            source_url=url,
            archive_url=None,
            validator_verdict="accepted",
            validator_confidence=None,
            dedup_key=dedup,
        )
        await append_signal(session, sig)
        written += 1

    # --- Score -----------------------------------------------------------
    composite_100 = float(output.get("composite_risk_score", 0.0)) * 10.0
    composite_100 = max(0.0, min(100.0, composite_100))

    prev = (
        await session.execute(
            select(VendorScore)
            .where(VendorScore.vendor_id == vendor.id)
            .order_by(VendorScore.computed_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    score = VendorScore(
        vendor_id=vendor.id,
        composite=composite_100,
        previous_composite=prev.composite if prev else None,
        delta=(composite_100 - prev.composite) if prev else None,
        computed_at=now,
        weights_version=PROVISIONAL_WEIGHTS_VERSION,
        thresholds_version=PROVISIONAL_THRESHOLDS_VERSION,
        engine_version=ENGINE_VERSION,
        excluded_signal_ids=[],
    )
    session.add(score)
    await session.flush()

    # --- Dimensions (raw only; baseline/z NULL, flagged) -----------------
    from db.models.score import ConfidenceTier

    for key, raw in dimensions.items():
        m = DIMENSION_MAP.get(key)
        if m is None:
            continue
        session.add(
            DimensionScore(
                vendor_score_id=score.id,
                vendor_id=vendor.id,
                dimension=m,
                raw_value=float(raw) * 10.0,  # same 0-10 -> 0-100 scaling
                baseline=None,  # NOT fabricated
                z_score=None,  # NOT fabricated
                anomaly_ratio=None,
                contribution=float(raw) * 10.0,
                weight_applied=1.0 / max(len(dimensions), 1),
                context_conditioned=False,
                confidence=ConfidenceTier.REPORTED,
                signal_ids=[],
            )
        )

    vendor.last_capture_at = now
    vendor.last_capture_ok = True

    return {
        "vendor": name,
        "vendor_id": str(vendor.id),
        "composite_0_100": composite_100,
        "signals_written": written,
        "dimensions_scored": [
            DIMENSION_MAP[k].value for k in dimensions if k in DIMENSION_MAP
        ],
        "baseline_provided": False,
    }


async def ingest_many(
    session: AsyncSession, org_id: uuid.UUID, outputs: list[dict]
) -> list[dict]:
    results = []
    for o in outputs:
        results.append(await ingest_pipeline_output(session, org_id, o))
    return results
