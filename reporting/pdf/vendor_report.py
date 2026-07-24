"""
Single-vendor pack.

Same components as the fleet pack, scoped to one vendor and with the full
signal timeline included — which the fleet pack omits for length. This is the
document you hand to someone asking about one specific vendor.
"""

from __future__ import annotations

import io
import uuid
from datetime import datetime, timezone

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, Table, TableStyle
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.integrity.hash_chain import head_hash_for_export
from db.models.artifact import NarrativeArtifact
from db.models.contract import Contract
from db.models.score import VendorScore
from db.models.vendor import Vendor
from reporting.pdf import components as C
from reporting.pdf.disclaimer import DISCLAIMER_BODY, DISCLAIMER_TITLE, cover_caveat
from reporting.pdf.evidence_pack import CONTENT_W, MARGIN, _Doc, _md_to_para

TIMELINE_LIMIT = 60


async def render_vendor_report(
    session: AsyncSession, org_id: uuid.UUID, vendor_id: uuid.UUID
) -> bytes:
    st = C.styles()
    generated_at = datetime.now(timezone.utc)
    head_hash = await head_hash_for_export(session)

    vendor = (
        await session.execute(
            select(Vendor).where(Vendor.id == vendor_id, Vendor.org_id == org_id)
        )
    ).scalar_one()

    score = (
        await session.execute(
            select(VendorScore)
            .options(selectinload(VendorScore.dimensions))
            .where(VendorScore.vendor_id == vendor_id)
            .order_by(VendorScore.computed_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    narrative = (
        await session.execute(
            select(NarrativeArtifact)
            .where(NarrativeArtifact.vendor_id == vendor_id)
            .order_by(NarrativeArtifact.generated_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    contract = (
        await session.execute(select(Contract).where(Contract.vendor_id == vendor_id))
    ).scalar_one_or_none()

    timeline = (
        await session.execute(
            text(
                """
                SELECT t.observed_at, t.event_date, t.metric::text AS metric,
                       t.source::text AS source, t.summary, t.source_url,
                       t.archive_url, t.is_superseded, t.chain_seq
                FROM signal_timeline t
                WHERE t.vendor_id = CAST(:vid AS uuid)
                  AND t.validator_verdict = 'accepted'
                ORDER BY t.observed_at DESC
                LIMIT CAST(:lim AS integer)
                """
            ),
            {"vid": str(vendor_id), "lim": TIMELINE_LIMIT},
        )
    ).mappings().all()

    story = [
        C.spacer(24),
        Paragraph(vendor.display_name, st["title"]),
        Paragraph("ICT third-party monitoring evidence — single vendor", st["subtitle"]),
        C.hrule(CONTENT_W),
        C.spacer(4),
        C.kv_table(
            [
                ("Legal name", vendor.legal_name),
                ("LEI", vendor.lei or "not recorded"),
                ("Entity type", str(vendor.entity_type.value).replace("_", " ")),
                ("Critical function", "yes" if vendor.is_critical else "no"),
                ("Last capture",
                 f"{vendor.last_capture_at:%Y-%m-%d %H:%M UTC}" if vendor.last_capture_at else "never"),
                ("Generated", f"{generated_at:%Y-%m-%d %H:%M:%S UTC}"),
            ],
            CONTENT_W,
        ),
        C.spacer(6),
        Paragraph("<b>Evidence chain head</b>", st["h2"]),
        Paragraph(head_hash, st["mono"]),
        C.spacer(4),
        Paragraph(f"<i>{cover_caveat()}</i>", st["small"]),
        PageBreak(),
    ]

    if score:
        story += [
            Paragraph("Score decomposition", st["h1"]),
            Paragraph(
                f"Composite <b>{score.composite:.1f}</b> computed "
                f"{score.computed_at:%Y-%m-%d %H:%M UTC} under weights "
                f"{score.weights_version}, thresholds {score.thresholds_version}, "
                f"engine {score.engine_version}.",
                st["body"],
            ),
            C.spacer(3),
            C.dimension_table(
                [
                    {
                        "dimension": d.dimension.value if hasattr(d.dimension, "value") else str(d.dimension),
                        "raw_value": d.raw_value,
                        "baseline": d.baseline,
                        "z_score": d.z_score,
                        "anomaly_ratio": d.anomaly_ratio,
                        "weight_applied": d.weight_applied,
                        "confidence": d.confidence.value if hasattr(d.confidence, "value") else str(d.confidence),
                    }
                    for d in score.dimensions
                ],
                CONTENT_W,
            ),
            C.spacer(5),
        ]

    if narrative:
        story += [
            Paragraph("Assessment", st["h1"]),
            Paragraph(_md_to_para(narrative.narrative_md), st["body"]),
            C.spacer(2),
            Paragraph(
                f"Model <b>{narrative.model_id}</b> · prompt {narrative.prompt_name} "
                f"({narrative.prompt_hash[:12]}…) · generated "
                f"{narrative.generated_at:%Y-%m-%d %H:%M UTC}. This assessment is "
                f"retrieved as issued; it is not regenerated on export.",
                st["small"],
            ),
            C.spacer(3),
        ] + C.citation_block(narrative.citations or [], CONTENT_W)
        story.append(PageBreak())

    # ---- Signal timeline --------------------------------------------------
    story += [
        Paragraph("Observation timeline", st["h1"]),
        Paragraph(
            f"Most recent {len(timeline)} accepted observations. Superseded "
            "observations are shown and marked — they are retained, never "
            "deleted, and excluded from scoring.",
            st["body"],
        ),
        C.spacer(3),
    ]

    header = ["Observed", "Event", "Metric", "Summary", "Seq"]
    data = [[Paragraph(f"<b>{h}</b>", st["small"]) for h in header]]
    for r in timeline:
        summary = r["summary"]
        if r["is_superseded"]:
            summary = f"<font color='{C.MUTED.hexval()[2:]}'><i>[superseded]</i> {summary}</font>"
        data.append([
            Paragraph(f"{r['observed_at']:%Y-%m-%d}", st["mono"]),
            Paragraph(f"{r['event_date']:%Y-%m-%d}", st["mono"]),
            Paragraph(str(r["metric"]).replace("_", " "), st["small"]),
            Paragraph(summary, st["small"]),
            Paragraph(str(r["chain_seq"]), st["mono"]),
        ])

    t = Table(data, colWidths=[CONTENT_W * x for x in (0.13, 0.13, 0.17, 0.49, 0.08)])
    t.setStyle(
        TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LINEBELOW", (0, 0), (-1, 0), 0.6, C.INK),
            ("LINEBELOW", (0, 1), (-1, -2), 0.25, C.RULE),
            ("TOPPADDING", (0, 0), (-1, -1), 2.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
        ])
    )
    story.append(t)

    if contract:
        story += [
            PageBreak(),
            Paragraph("Register fields", st["h1"]),
            Paragraph(
                "Contractual data recorded for the Article 28(3) register, joined "
                "to the live monitoring above. These fields are entered and "
                "confirmed by an analyst.",
                st["body"],
            ),
            C.spacer(3),
            C.kv_table(
                [
                    ("Arrangement reference", contract.contractual_arrangement_ref),
                    ("Provider LEI", contract.provider_lei),
                    ("Provider country", contract.provider_country),
                    ("Function identifier", contract.function_identifier),
                    ("Supports critical function", "yes" if contract.supports_critical_function else "no"),
                    ("Start date", contract.start_date),
                    ("End date", contract.end_date),
                    ("Notice period (days)", contract.notice_period_days),
                    ("Governing law", contract.governing_law_country),
                    ("Data locations", ", ".join(contract.data_location_countries or []) or None),
                    ("Substitutability",
                     contract.substitutability.value.replace("_", " ") if contract.substitutability else None),
                    ("Exit plan exists", "yes" if contract.exit_plan_exists else "no"),
                    ("Exit plan last tested", contract.exit_plan_last_tested),
                    ("Register version", contract.register_version),
                ],
                CONTENT_W,
            ),
        ]

    story += [
        PageBreak(),
        Paragraph(DISCLAIMER_TITLE, st["h1"]),
        Paragraph(DISCLAIMER_BODY, st["body"]),
    ]

    buf = io.BytesIO()
    doc = _Doc(buf, generated_at, head_hash,
               leftMargin=MARGIN, rightMargin=MARGIN,
               topMargin=MARGIN, bottomMargin=MARGIN + 8 * mm,
               title=f"Troy — {vendor.display_name}", author="Troy")
    doc.build(story)
    return buf.getvalue()