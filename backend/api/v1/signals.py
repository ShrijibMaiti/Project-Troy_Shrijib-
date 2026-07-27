"""
Signal timeline and the dispute/supersede endpoint.

Reads from the signal_timeline VIEW, not the signals table — the view joins
corrections so superseded rows come back flagged rather than hidden. Wrik's
scoring engine reads signal_current instead, which excludes them.

The dispute endpoint is append-only by construction: it INSERTS a correction
row. The original signal is never touched. That is why the UI must say
"supersede and annotate", never "edit".
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select, text

from backend.deps import DB, CurrentOrg, Writer, write_audit
from backend.schemas import DisputeIn, DisputeOut, SignalTimelineItem
from db.models.audit_log import AuditAction
from db.models.correction import Correction, CorrectionReason
from db.models.score import VendorScore
from db.models.signal import Signal
from db.models.vendor import Vendor

router = APIRouter(prefix="/signals", tags=["signals"])


@router.get("/vendor/{vendor_id}", response_model=list[SignalTimelineItem])
async def vendor_timeline(
    vendor_id: uuid.UUID,
    session: DB,
    org: CurrentOrg,
    metric: str | None = None,
    include_rejected: bool = False,
    limit: int = Query(200, le=1000),
    offset: int = 0,
) -> list[SignalTimelineItem]:
    await _assert_owned(session, org, vendor_id)

    sql = """
        SELECT t.*, e.text AS excerpt_text
        FROM signal_timeline t
        LEFT JOIN excerpts e ON e.id = t.excerpt_id
        WHERE t.vendor_id = CAST(:vid AS uuid)
          AND (CAST(:metric AS text) IS NULL OR t.metric::text = CAST(:metric AS text))
          AND (CAST(:incl AS boolean) OR t.validator_verdict = 'accepted')
        ORDER BY t.observed_at DESC, t.chain_seq DESC
        LIMIT CAST(:limit AS integer) OFFSET CAST(:offset AS integer)
    """
    rows = (
        await session.execute(
            text(sql),
            {
                "vid": str(vendor_id),
                "metric": metric,
                "incl": include_rejected,
                "limit": limit,
                "offset": offset,
            },
        )
    ).mappings()

    return [SignalTimelineItem(**dict(r)) for r in rows]


@router.get("/{signal_id}", response_model=SignalTimelineItem)
async def get_signal(
    signal_id: uuid.UUID, session: DB, org: CurrentOrg
) -> SignalTimelineItem:
    row = (
        (
            await session.execute(
                text(
                    """
                SELECT t.*, e.text AS excerpt_text
                FROM signal_timeline t
                LEFT JOIN excerpts e ON e.id = t.excerpt_id
                JOIN vendors v ON v.id = t.vendor_id
                WHERE t.id = CAST(:sid AS uuid) AND v.org_id = CAST(:oid AS uuid)
                """
                ),
                {"sid": str(signal_id), "oid": str(org.org_id)},
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Signal not found")
    return SignalTimelineItem(**dict(row))


@router.post("/{signal_id}/dispute", response_model=DisputeOut)
async def dispute_signal(
    signal_id: uuid.UUID, body: DisputeIn, session: DB, org: Writer
) -> DisputeOut:
    """
    Mark a signal as wrong.

    One mechanism, two problems solved: the analyst override the methodology
    needed, and the correction route the defamation exposure needed.
    """
    sig = (
        await session.execute(
            select(Signal)
            .join(Vendor, Vendor.id == Signal.vendor_id)
            .where(Signal.id == signal_id, Vendor.org_id == org.org_id)
        )
    ).scalar_one_or_none()
    if sig is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Signal not found")

    existing = (
        await session.execute(
            select(Correction).where(Correction.signal_id == signal_id)
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "This signal has already been superseded"
        )

    latest = (
        await session.execute(
            select(VendorScore)
            .where(VendorScore.vendor_id == sig.vendor_id)
            .order_by(VendorScore.computed_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    score_before = latest.composite if latest else None

    corr = Correction(
        signal_id=signal_id,
        reason=CorrectionReason(body.reason),
        note=body.note,
        actor=org.actor,
        actor_email=org.actor_email,
        org_id=org.org_id,
        score_before=score_before,
    )
    session.add(corr)
    await session.flush()

    # Recompute is queued, not inline: scoring belongs to Wrik's engine and
    # can be slow. The UI polls or listens on SSE for the updated score.
    recomputed = False
    try:
        from backend.jobs.runner import enqueue

        await enqueue("recompute_score", str(sig.vendor_id))
        recomputed = True
    except Exception:
        pass  # queue unavailable; score refreshes on the next scheduled run

    await write_audit(
        session,
        org,
        AuditAction.SIGNAL_DISPUTED,
        entity_type="signal",
        entity_id=signal_id,
        detail={"reason": body.reason, "vendor_id": str(sig.vendor_id)},
        note=body.note,
    )

    return DisputeOut(
        correction_id=corr.id,
        signal_id=signal_id,
        score_before=score_before,
        score_after=None,
        recomputed=recomputed,
    )


async def _assert_owned(session, org, vendor_id: uuid.UUID) -> None:
    ok = (
        await session.execute(
            select(Vendor.id).where(Vendor.id == vendor_id, Vendor.org_id == org.org_id)
        )
    ).scalar_one_or_none()
    if ok is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Vendor not found")
