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
            await publish(
                vendor.org_id, "job.failed", {"vendor_id": vendor_id, "error": str(exc)}
            )
            raise

        org_id = vendor.org_id

    if ok:
        await recompute_score(ctx, vendor_id)

    await publish(
        org_id,
        "capture.finished",
        {"vendor_id": vendor_id, "written": written, **detail},
    )
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

        score = await score_vendor(
            session, vendor, weights=weights, thresholds=thresholds
        )
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
    """
    Render and store an export.
    Content-addressed: if the same inputs produced an export before, this is a
    lookup, not a render. That is both the correctness rule (an issued document
    is immutable) and the fix for the original's 130-second cold export.
    """
    import uuid as _uuid

    from db.integrity.hash_chain import head_hash_for_export
    from db.models.export_artifact import ExportFormat, ExportKind
    from reporting import artifacts as art

    oid = _uuid.UUID(org_id)
    await publish(oid, "job.progress", {"stage": "export", "format": fmt, "pct": 10})
    async with SessionFactory() as session:
        head = await head_hash_for_export(session)
        # Everything that determines the output. Two exports with the same
        # input hash MUST produce identical bytes.
        from sqlalchemy import func as _f

        from db.models.contract import Contract as _C
        from db.models.score import VendorScore as _S

        max_score = (
            await session.execute(
                select(_f.max(_S.computed_at))
                .join(Vendor, Vendor.id == _S.vendor_id)
                .where(Vendor.org_id == oid)
            )
        ).scalar_one_or_none()
        max_reg = (
            await session.execute(
                select(_f.max(_C.register_version)).where(_C.org_id == oid)
            )
        ).scalar_one_or_none()
        input_hash = art.compute_input_hash(
            {
                "org": org_id,
                "fmt": fmt,
                "chain_head": head,
                "latest_score_at": max_score,
                "register_version": max_reg,
            }
        )
        existing = await art.find_existing(session, oid, input_hash)
        if existing is not None:
            await publish(
                oid,
                "job.done",
                {"stage": "export", "artifact_id": str(existing.id), "cached": True},
            )
            return {
                "org_id": org_id,
                "format": fmt,
                "cached": True,
                "artifact_id": str(existing.id),
                "content_hash": existing.content_hash,
            }
        await publish(oid, "job.progress", {"stage": "export", "pct": 40})
        if fmt == "its":
            from reporting.its_export.writer import write_its_register

            payload = await write_its_register(session, oid, fmt="csv")
            kind, ext, efmt = ExportKind.ITS_REGISTER, "zip", ExportFormat.ITS_CSV
        elif fmt == "its_json":
            from reporting.its_export.writer import write_its_register

            payload = await write_its_register(session, oid, fmt="json")
            kind, ext, efmt = ExportKind.ITS_REGISTER, "json", ExportFormat.ITS_JSON
        else:
            from reporting.pdf.evidence_pack import render_evidence_pack

            payload = await render_evidence_pack(session, oid)
            kind, ext, efmt = ExportKind.EVIDENCE_PACK, "pdf", ExportFormat.PDF
        await publish(oid, "job.progress", {"stage": "export", "pct": 80})
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
        stored = await art.store(
            session,
            org_id=oid,
            vendor_id=None,
            kind=kind,
            fmt=efmt,
            payload=payload,
            input_hash=input_hash,
            chain_head_hash=head,
            filename=f"troy-{kind.value}-{stamp}.{ext}",
            generated_by="system",
            detail={"register_version": max_reg},
        )
        await session.commit()
    await publish(
        oid,
        "job.done",
        {"stage": "export", "artifact_id": str(stored.id), "cached": stored.from_cache},
    )
    return {
        "org_id": org_id,
        "format": fmt,
        "artifact_id": str(stored.id),
        "content_hash": stored.content_hash,
        "size_bytes": stored.size_bytes,
        "cached": stored.from_cache,
    }


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
