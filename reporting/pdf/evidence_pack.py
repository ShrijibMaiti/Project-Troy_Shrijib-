"""
The fleet-wide evidence pack.

Structure:
  1. Cover — org, generation time, CHAIN HEAD HASH, standing caveat
  2. Fleet audit — every vendor, score, freshness, open alerts
  3. Per-vendor sections — narrative with numbered citations, decomposition
  4. Trust metrics — both audit numbers, chain verification result
  5. Methodology appendix — weights, derivation, stated limitations
  6. Basis and limitations — the full disclaimer

Deliberate ordering: the chain head hash appears on page one, before any
claim. A reader should know how to verify the document before reading what it
asserts.
"""

from __future__ import annotations

import io
import uuid
from datetime import datetime, timezone

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Table,
    TableStyle,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.config import settings
from db.integrity.hash_chain import head_hash_for_export, verify_chain
from db.models.alert import Alert
from db.models.artifact import NarrativeArtifact
from db.models.contract import Contract
from db.models.org import Org
from db.models.score import VendorScore
from db.models.vendor import Vendor
from reporting.pdf import components as C
from reporting.pdf.disclaimer import (
    DISCLAIMER_BODY,
    DISCLAIMER_TITLE,
    INTEGRITY_NOTICE,
    cover_caveat,
    footer_line,
)

PAGE_W, PAGE_H = A4
MARGIN = 20 * mm
CONTENT_W = PAGE_W - 2 * MARGIN


class _Doc(BaseDocTemplate):
    """Footer on every page carries the head hash. Not optional."""

    def __init__(self, buf, generated_at: datetime, head_hash: str, **kw):
        super().__init__(buf, pagesize=A4, **kw)
        self.generated_at = generated_at
        self.head_hash = head_hash
        frame = Frame(MARGIN, MARGIN + 8 * mm, CONTENT_W, PAGE_H - 2 * MARGIN - 8 * mm, id="main")
        self.addPageTemplates([PageTemplate(id="std", frames=[frame], onPage=self._footer)])

    def _footer(self, canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 6.5)
        canvas.setFillColor(C.MUTED)
        canvas.drawString(
            MARGIN, MARGIN, footer_line(doc.page, self.generated_at, self.head_hash)
        )
        canvas.restoreState()


async def render_evidence_pack(session: AsyncSession, org_id: uuid.UUID) -> bytes:
    """
    Render the fleet-wide pack. Returns PDF bytes.

    Callers store via reporting.artifacts.store(); this function does not
    persist anything, so it can be called from a test without side effects.
    """
    st = C.styles()
    generated_at = datetime.now(timezone.utc)

    org = (await session.execute(select(Org).where(Org.id == org_id))).scalar_one()
    head_hash = await head_hash_for_export(session)
    chain = await verify_chain(session)

    vendors = list(
        (
            await session.execute(
                select(Vendor)
                .where(Vendor.org_id == org_id, Vendor.is_active)
                .order_by(Vendor.display_name)
            )
        ).scalars()
    )
    ids = [v.id for v in vendors]

    scores: dict[uuid.UUID, VendorScore] = {}
    narratives: dict[uuid.UUID, NarrativeArtifact] = {}
    alerts: dict[uuid.UUID, int] = {}
    contracts: dict[uuid.UUID, Contract] = {}

    if ids:
        latest = (
            select(VendorScore.vendor_id, func.max(VendorScore.computed_at).label("mx"))
            .where(VendorScore.vendor_id.in_(ids))
            .group_by(VendorScore.vendor_id)
            .subquery()
        )
        for s in (
            await session.execute(
                select(VendorScore)
                .options(selectinload(VendorScore.dimensions))
                .join(latest, (VendorScore.vendor_id == latest.c.vendor_id)
                      & (VendorScore.computed_at == latest.c.mx))
            )
        ).scalars():
            scores[s.vendor_id] = s

        for a in (
            await session.execute(
                select(NarrativeArtifact)
                .where(NarrativeArtifact.vendor_id.in_(ids))
                .order_by(NarrativeArtifact.generated_at.desc())
            )
        ).scalars():
            narratives.setdefault(a.vendor_id, a)

        alerts = dict(
            (
                await session.execute(
                    select(Alert.vendor_id, func.count(Alert.id))
                    .where(Alert.vendor_id.in_(ids), Alert.is_open)
                    .group_by(Alert.vendor_id)
                )
            ).all()
        )
        contracts = {
            c.vendor_id: c
            for c in (
                await session.execute(select(Contract).where(Contract.vendor_id.in_(ids)))
            ).scalars()
        }

    story: list = []

    # ---- 1. Cover ---------------------------------------------------------
    story += [
        C.spacer(30),
        Paragraph("ICT Third-Party<br/>Monitoring Evidence Pack", st["title"]),
        Paragraph(
            "Continuous monitoring evidence prepared to attach to a register of "
            "information maintained under Article 28(3) of Regulation (EU) 2022/2554.",
            st["subtitle"],
        ),
        C.hrule(CONTENT_W),
        C.spacer(6),
        C.kv_table(
            [
                ("Organisation", org.name),
                ("Generated", f"{generated_at:%Y-%m-%d %H:%M:%S UTC}"),
                ("Vendors in scope", str(len(vendors))),
                ("Critical vendors", str(sum(1 for v in vendors if v.is_critical))),
                ("Open alerts", str(sum(alerts.values()))),
            ],
            CONTENT_W,
        ),
        C.spacer(8),
        Paragraph("<b>Evidence chain head</b>", st["h2"]),
        Paragraph(head_hash, st["mono"]),
        Paragraph(
            f"Chain verification at generation: "
            f"<b>{'PASSED' if chain.ok else 'FAILED'}</b> — {chain.checked} records walked."
            + ("" if chain.ok else f" First break at sequence {chain.first_break_seq}: {chain.reason}"),
            st["small"],
        ),
        C.spacer(6),
        Paragraph(INTEGRITY_NOTICE, st["small"]),
        C.spacer(8),
        Paragraph(f"<i>{cover_caveat()}</i>", st["small"]),
        PageBreak(),
    ]

    # ---- 2. Fleet audit ---------------------------------------------------
    story.append(Paragraph("Fleet audit", st["h1"]))
    story.append(
        Paragraph(
            "Scores are relative to each vendor's own trailing baseline, not to "
            "one another. A vendor is flagged stale where no successful capture "
            "has completed in the last three days — staleness is reported "
            "because stale data is the condition this system exists to detect.",
            st["body"],
        )
    )
    story.append(C.spacer(3))

    header = ["Vendor", "Type", "Score", "Δ", "Last capture", "Alerts", "Register"]
    data = [[Paragraph(f"<b>{h}</b>", st["small"]) for h in header]]

    for v in vendors:
        s = scores.get(v.id)
        stale_days = (generated_at - v.last_capture_at).days if v.last_capture_at else None
        capture_txt = (
            "never" if stale_days is None
            else "today" if stale_days == 0
            else f"{stale_days}d ago"
        )
        if stale_days is None or stale_days >= 3:
            capture_txt = f"<font color='{C.RISK_MED.hexval()[2:]}'>{capture_txt}</font>"

        c = contracts.get(v.id)
        reg = "complete" if c else "not filed"

        colour = C.risk_color(s.composite if s else None).hexval()[2:]
        data.append([
            Paragraph(v.display_name, st["small"]),
            Paragraph(str(v.entity_type.value).replace("_", " "), st["small"]),
            Paragraph(
                f"<font color='{colour}'><b>{s.composite:.1f}</b></font>" if s else "—",
                st["small"],
            ),
            Paragraph(f"{s.delta:+.1f}" if s and s.delta is not None else "—", st["mono"]),
            Paragraph(capture_txt, st["small"]),
            Paragraph(str(alerts.get(v.id, 0)), st["mono"]),
            Paragraph(reg, st["small"]),
        ])

    t = Table(data, colWidths=[CONTENT_W * x for x in (0.26, 0.13, 0.11, 0.09, 0.16, 0.10, 0.15)])
    t.setStyle(
        TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LINEBELOW", (0, 0), (-1, 0), 0.6, C.INK),
            ("LINEBELOW", (0, 1), (-1, -2), 0.25, C.RULE),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ])
    )
    story += [t, PageBreak()]

    # ---- 3. Per-vendor ----------------------------------------------------
    for v in vendors:
        s = scores.get(v.id)
        n = narratives.get(v.id)

        block = [
            Paragraph(v.display_name, st["h1"]),
            Paragraph(
                f"{v.legal_name}"
                + (f" · LEI {v.lei}" if v.lei else " · no LEI recorded")
                + f" · {str(v.entity_type.value).replace('_', ' ')}",
                st["small"],
            ),
            C.hrule(CONTENT_W),
            C.spacer(3),
        ]

        if s:
            block += [
                Paragraph(
                    f"Composite <b>{s.composite:.1f}</b>"
                    + (f" ({s.delta:+.1f} since previous)" if s.delta is not None else "")
                    + f" · computed {s.computed_at:%Y-%m-%d} · "
                    f"weights {s.weights_version} · thresholds {s.thresholds_version}",
                    st["body"],
                ),
                C.spacer(2),
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
                        for d in s.dimensions
                    ],
                    CONTENT_W,
                ),
                C.spacer(4),
            ]
        else:
            block.append(
                Paragraph(
                    "No score computed. This vendor has not been captured and "
                    "scored, or calibration is unavailable.",
                    st["small"],
                )
            )

        if n:
            block += [
                Paragraph("Assessment", st["h2"]),
                Paragraph(_md_to_para(n.narrative_md), st["body"]),
                C.spacer(2),
                Paragraph(
                    f"Generated {n.generated_at:%Y-%m-%d %H:%M UTC} · model "
                    f"<b>{n.model_id}</b> · prompt {n.prompt_name} "
                    f"({n.prompt_hash[:12]}…)"
                    + (" · deterministic fallback" if n.is_fallback else ""),
                    st["small"],
                ),
                C.spacer(3),
            ] + C.citation_block(n.citations or [], CONTENT_W)
        else:
            block.append(
                Paragraph(
                    "No assessment generated for this vendor.", st["small"]
                )
            )

        story += block
        story.append(PageBreak())

    # ---- 4. Trust metrics -------------------------------------------------
    m = (
        await session.execute(
            select(
                func.avg(NarrativeArtifact.citation_resolution_pct),
                func.sum(NarrativeArtifact.distinct_claims),
                func.sum(NarrativeArtifact.distinct_citations),
                func.sum(NarrativeArtifact.unresolved_count),
                func.avg(NarrativeArtifact.entailment_fidelity_pct),
                func.sum(NarrativeArtifact.entailment_sampled),
                func.sum(NarrativeArtifact.entailment_failed),
            )
            .join(Vendor, Vendor.id == NarrativeArtifact.vendor_id)
            .where(Vendor.org_id == org_id)
        )
    ).first()

    story += [
        Paragraph("Verification", st["h1"]),
        Paragraph(
            "Two independent measures are reported. Citation resolution proves "
            "each numbered claim maps to a stored observation. Extraction "
            "fidelity proves the stored observation is supported by the source "
            "excerpt it was taken from. The second is the measure that catches "
            "extraction error; the first alone would certify a faithfully-cited "
            "but incorrectly-extracted claim.",
            st["body"],
        ),
        C.spacer(3),
        C.audit_metrics_block(
            {
                "narrative_resolution_pct": float(m[0]) if m and m[0] is not None else None,
                "distinct_claims": int(m[1] or 0) if m else 0,
                "distinct_citations": int(m[2] or 0) if m else 0,
                "unresolved_count": int(m[3] or 0) if m else 0,
                "extraction_fidelity_pct": float(m[4]) if m and m[4] is not None else None,
                "entailment_sampled": int(m[5] or 0) if m else 0,
                "entailment_failed": int(m[6] or 0) if m else 0,
            },
            CONTENT_W,
        ),
        C.spacer(6),
        Paragraph("Evidence chain", st["h2"]),
        C.kv_table(
            [
                ("Verification result", "PASSED" if chain.ok else "FAILED"),
                ("Records walked", str(chain.checked)),
                ("Head sequence", str(chain.head_seq)),
                ("Head hash", chain.head_hash),
            ]
            + ([] if chain.ok else [("First break", f"seq {chain.first_break_seq}: {chain.reason}")]),
            CONTENT_W,
        ),
        PageBreak(),
    ]

    # ---- 5. Methodology ---------------------------------------------------
    story += _methodology_section(st)

    # ---- 6. Disclaimer ----------------------------------------------------
    story += [
        PageBreak(),
        Paragraph(DISCLAIMER_TITLE, st["h1"]),
        Paragraph(DISCLAIMER_BODY, st["body"]),
    ]

    buf = io.BytesIO()
    doc = _Doc(buf, generated_at, head_hash,
               leftMargin=MARGIN, rightMargin=MARGIN,
               topMargin=MARGIN, bottomMargin=MARGIN + 8 * mm,
               title=f"Troy Evidence Pack — {org.name}",
               author="Troy", subject="ICT third-party monitoring evidence")
    doc.build(story)
    return buf.getvalue()


def _methodology_section(st) -> list:
    weights = settings.load_calibration("weights")
    thresholds = settings.load_calibration("thresholds")
    lead_time = settings.load_calibration("lead_time")

    out = [
        Paragraph("Methodology", st["h1"]),
        Paragraph(
            "Six dimensions are scored against each vendor's own twelve-month "
            "trailing baseline. Volume-based dimensions are normalised into an "
            "anomaly ratio so that larger organisations, which naturally "
            "generate more coverage, are not penalised for their size. "
            "Dimension weights are context-conditioned: a dimension's weight "
            "depends on which other dimensions moved in the same window.",
            st["body"],
        ),
        C.spacer(3),
    ]

    if weights:
        out += [
            Paragraph("Dimension weights", st["h2"]),
            C.kv_table(
                [(k.replace("_", " "), str(v)) for k, v in (weights.get("weights") or weights).items()
                 if not k.startswith("_")],
            ),
            C.spacer(3),
        ]
    else:
        out.append(
            Paragraph(
                "<b>Weights are not calibrated.</b> Scores in this document are "
                "PROVISIONAL and derived from provisional constants. No claim is "
                "made about their predictive validity.",
                st["body"],
            )
        )

    if thresholds:
        out += [
            Paragraph("Alert thresholds", st["h2"]),
            C.kv_table([(k.replace("_", " "), str(v)) for k, v in thresholds.items()
                        if not k.startswith("_")]),
            C.spacer(3),
        ]

    if lead_time:
        out += [
            Paragraph("Backtest result", st["h2"]),
            C.kv_table([
                ("Median lead time", f"{lead_time.get('median_lead_days', '—')} days"),
                ("Events tested", str(lead_time.get("events_tested", "—"))),
                ("Control vendors", str(lead_time.get("controls", "—"))),
                ("Control false-positive rate", str(lead_time.get("control_fp_rate", "—"))),
            ]),
            Paragraph(
                "Backtest evidence is directional, not statistical. A small event "
                "set supports the claim that the score moved before observed "
                "deterioration; it does not support a precision claim.",
                st["small"],
            ),
            C.spacer(3),
        ]
    else:
        out.append(
            Paragraph(
                "<b>No backtest has been run.</b> The claim that these signals "
                "lead conventional indicators is, at the date of this document, "
                "unvalidated.",
                st["body"],
            )
        )

    out += [
        C.spacer(3),
        Paragraph("Stated limitations", st["h2"]),
        Paragraph(
            "· Public-signal monitoring only. An organisation aware of being "
            "monitored can suppress some signals; weighting favours sources that "
            "are difficult to suppress, such as court dockets and regulatory filings.<br/>"
            "· Private companies have no securities-filing coverage. The private-"
            "company source tier is materially thinner than public-company coverage.<br/>"
            "· Scores are relative to each vendor's own history, not to peers.<br/>"
            "· This document is monitoring evidence that attaches to a register of "
            "information. It is not itself a register of information.",
            st["body"],
        ),
    ]
    return out


def _md_to_para(md: str) -> str:
    """
    Minimal markdown → ReportLab inline markup.

    Deliberately minimal: citation markers [1] must survive untouched, and
    escaping is more important than fidelity — an unescaped angle bracket in
    scraped text would break the paragraph parser.
    """
    import re

    s = md.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<i>\1</i>", s)
    s = s.replace("\n\n", "<br/><br/>").replace("\n", " ")
    return s