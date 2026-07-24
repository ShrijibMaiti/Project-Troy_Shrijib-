"""
The pipeline: capture → validate → score → narrate → alert → export.

IMPORTANT — Wrik's domains (capture/, ai/, scoring/) may not exist yet. Every
import of his code is guarded, and a missing module produces a DEGRADED result
rather than a crash. This lets the whole backend boot, serve, and be tested
against the real database before the intelligence pipeline lands.

Each task publishes progress to SSE. Publishing is fire-and-forget: a failed
publish never fails the job.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from backend.api.sse import publish
from backend.config import settings
from db.models.alert import Alert
from db.models.audit_log import AuditAction, AuditLog
from db.models.vendor import Vendor
from db.session import SessionFactory


# ---------------------------------------------------------------------------
# Guarded imports of Wrik's modules
# ---------------------------------------------------------------------------

def _try_import(path: str, name: str):
    try:
        mod = __import__(path, fromlist=[name])
        return getattr(mod, name)
    except Exception:
        return None


capture_vendor_signals = _try_import("capture.orchestrator", "capture_vendor_signals")
validate_signals = _try_import("ai.validator", "validate_signals")
score_vendor = _try_import("scoring.engine", "score_vendor")
write_narrative = _try_import("ai.narrator", "write_narrative")
run_citation_audit = _try_import("ai.citation_audit", "run_citation_audit")
run_entailment_audit = _try_import("ai.entailment_audit", "run_entailment_audit")


def _missing() -> list[str]:
    m = []
    if capture_vendor_signals is None:
        m.append("capture.orchestrator")
    if validate_signals is None:
        m.append("ai.validator")
    if score_vendor is None:
        m.append("scoring.engine")
    if write_narrative is None:
        m.append("ai.narrator")
    return m


async def _audit(session, action, org_id, **kw) -> None:
    session.add(AuditLog(action=action, actor="system", org_id=org_id, **kw))


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------

async def run_capture(ctx: dict, org_id: str | None = None) -> dict:
    """
    The daily 07:00 UTC entrypoint. Fans out one job per vendor.

    Fan-out rather than a single long job, so one vendor's failure never kills
    the run and each vendor gets its own retry budget.
    """
    from backend.jobs.runner import enqueue

    async with SessionFactory() as session:
        stmt = select(Vendor).where(Vendor.is_active, Vendor.capture_enabled)
        if org_id:
            stmt = stmt.where(Vendor.org_id == uuid.UUID(org_id))
        vendors = list((await session.execute(stmt)).scalars())

        for v in vendors:
            await _audit(
                session,
                AuditAction.CAPTURE_RUN,
                v.org_id,
                entity_type="vendor",
                entity_id=v.id,
                detail={"scheduled": True},
            )
        await session.commit()

    for v in vendors:
        await enqueue("capture_vendor", str(v.id))
        await publish(v.org_id, "capture.started", {"vendor_id": str(v.id)})

    return {
        "vendors_queued": len(vendors),
        "degraded": _missing(),
        "at": datetime.now(timezone.utc).isoformat(),
    }


async def capture_vendor(ctx: dict, vendor_id: str) -> dict:
    """
    One vendor: capture → validate → persist → score → narrate → alert.

    last_capture_ok is recorded whatever happens. A silent failure that leaves
    a stale vendor looking fresh is worse than a visible red flag.
    """
    vid = uuid.UUID(vendor_id)
    ok = False
    written = 0
    detail: dict[str, Any] = {}

    async with SessionFactory() as session:
        vendor = (
            await session.execute(select(Vendor).where(Vendor.id == vid))
        ).scalar_one_or_none()
        if vendor is None:
            return {"error": "vendor not found", "vendor_id": vendor_id}

        try:
            if capture_vendor_signals is None:
                detail["skipped"] = "capture.orchestrator not implemented"
            else:
                candidates = await capture_vendor_signals(session, vendor)
                detail["candidates"] = len(candidates)

                if validate_signals is not None:
                    accepted = await validate_signals(session, candidates)
                else:
                    accepted = candidates
                detail["accepted"] = len(accepted)
                written = len(accepted)
                ok = True

            vendor.last_capture_at = datetime.now(timezone.utc)
            vendor.last_capture_ok = ok
            await session.commit()

        except Exception as exc:
            await session.rollback()
            async with SessionFactory() as s2:
                v2 = (
                    await s2.execute(select(Vendor).where(Vendor.id == vid))
                ).scalar_one()
                v2.last_capture_at = datetime.now(timezone.utc)
                v2.last_capture_ok = False
                await s2.commit()
            await publish(vendor.org_id, "job.failed", {"vendor_id": vendor_id, "error": str(exc)})
            raise

        org_id = vendor.org_id

    if ok:
        await recompute_score(ctx, vendor_id)

    await publish(org_id, "capture.finished", {"vendor_id": vendor_id, "written": written, **detail})
    return {"vendor_id": vendor_id, "ok": ok, "written": written, **detail}


async def recompute_score(ctx: dict, vendor_id: str) -> dict:
    """
    Score from signal_current — the view that excludes superseded signals.
    Also called after a dispute, which is why it's a separate task.
    """
    vid = uuid.UUID(vendor_id)

    if score_vendor is None:
        return {"vendor_id": vendor_id, "skipped": "scoring.engine not implemented"}

    weights = settings.load_calibration("weights")
    thresholds = settings.load_calibration("thresholds")
    if not weights or not thresholds:
        return {
            "vendor_id": vendor_id,
            "skipped": "calibration missing — scores would not be reproducible",
        }

    async with SessionFactory() as session:
        vendor = (
            await session.execute(select(Vendor).where(Vendor.id == vid))
        ).scalar_one_or_none()
        if vendor is None:
            return {"error": "vendor not found"}

        score = await score_vendor(session, vendor, weights=weights, thresholds=thresholds)
        await _audit(
            session,
            AuditAction.SCORE_COMPUTED,
            vendor.org_id,
            entity_type="vendor",
            entity_id=vid,
            detail={"composite": getattr(score, "composite", None)},
        )
        await session.commit()

        await publish(
            vendor.org_id,
            "score.updated",
            {"vendor_id": vendor_id, "composite": getattr(score, "composite", None)},
        )

        alerts = list(
            (
                await session.execute(
                    select(Alert).where(Alert.vendor_id == vid, Alert.is_open)
                )
            ).scalars()
        )

    for a in alerts:
        if a.notified_at is None:
            await _notify(a)

    from backend.jobs.runner import enqueue

    await enqueue("generate_narrative", vendor_id)
    return {"vendor_id": vendor_id, "composite": getattr(score, "composite", None)}


async def generate_narrative(ctx: dict, vendor_id: str) -> dict:
    """
    Generate ONCE and freeze.

    The artifact records model_id, prompt_hash and input signal ids. There is
    no code path anywhere that regenerates a stored artifact — reproduction is
    retrieval.
    """
    if write_narrative is None:
        return {"vendor_id": vendor_id, "skipped": "ai.narrator not implemented"}

    vid = uuid.UUID(vendor_id)
    async with SessionFactory() as session:
        vendor = (
            await session.execute(select(Vendor).where(Vendor.id == vid))
        ).scalar_one_or_none()
        if vendor is None:
            return {"error": "vendor not found"}

        artifact = await write_narrative(session, vendor)

        if run_citation_audit is not None:
            await run_citation_audit(session, artifact)
        if run_entailment_audit is not None:
            await run_entailment_audit(session, artifact)

        await _audit(
            session,
            AuditAction.ARTIFACT_GENERATED,
            vendor.org_id,
            entity_type="artifact",
            entity_id=artifact.id,
            detail={
                "model_id": artifact.model_id,
                "prompt_hash": artifact.prompt_hash[:16],
            },
        )
        await session.commit()
        org_id = vendor.org_id

    await publish(org_id, "narrative.generated", {"vendor_id": vendor_id})
    return {"vendor_id": vendor_id, "artifact_id": str(artifact.id)}


async def export_register(ctx: dict, org_id: str, fmt: str = "pdf") -> dict:
    """Domain 7 owns the renderers; this is the queue seam."""
    oid = uuid.UUID(org_id)
    await publish(oid, "job.progress", {"stage": "export", "format": fmt, "pct": 10})

    try:
        if fmt == "its":
            from reporting.its_export.writer import write_its_register as render
        else:
            from reporting.pdf.evidence_pack import render_evidence_pack as render
    except Exception as exc:
        await publish(oid, "job.failed", {"stage": "export", "error": str(exc)})
        return {"skipped": f"reporting module not implemented: {exc}"}

    async with SessionFactory() as session:
        path = await render(session, oid)
        await session.commit()

    await publish(oid, "job.done", {"stage": "export", "path": str(path)})
    return {"org_id": org_id, "format": fmt, "path": str(path)}


async def verify_chain_job(ctx: dict) -> dict:
    """Scheduled integrity check. A break must be found by us, not by an auditor."""
    from db.integrity.hash_chain import verify_chain

    async with SessionFactory() as session:
        result = await verify_chain(session)
        session.add(
            AuditLog(
                action=AuditAction.CHAIN_VERIFIED,
                actor="system",
                detail=result.as_dict(),
            )
        )
        await session.commit()

    if not result.ok:
        print(f"[worker] CHAIN BREAK at seq={result.first_break_seq}: {result.reason}")
    return result.as_dict()


async def _notify(alert: Alert) -> None:
    """
    Dark until calibration exists. Alerting an uncalibrated score distributes
    noise faster; config.validate_runtime() refuses to boot in that state.
    """
    if not settings.notify_enabled:
        return
    from backend.notify.base import dispatch

    await dispatch(alert)