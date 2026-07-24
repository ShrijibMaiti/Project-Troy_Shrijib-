"""
Shared ReportLab building blocks.

Design intent: this should read like a well-set financial report, not a SaaS
dashboard export. Dense, typographic, restrained. Three risk colours only, and
red rare enough that it means something.

Fonts: General Sans + Sometype Mono, the same as the frontend, so the screen
and the export are visibly one object. Falls back to Helvetica/Courier if the
TTFs are absent — a missing font must never break an export.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

FONT_DIR = Path(__file__).parent / "fonts"

# ---- Palette. Restrained on purpose. --------------------------------------
INK = colors.HexColor("#1A1A1A")
MUTED = colors.HexColor("#6B6B6B")
RULE = colors.HexColor("#D8D6D1")
PAPER = colors.HexColor("#FAF9F7")

RISK_LOW = colors.HexColor("#3D6B4A")
RISK_MED = colors.HexColor("#B07D2B")
RISK_HIGH = colors.HexColor("#9B3232")

TIER_COLORS = {
    "verified": RISK_LOW,
    "reported": RISK_MED,
    "unconfirmed": MUTED,
}

_fonts_registered = False


def register_fonts() -> tuple[str, str]:
    """
    Returns (body_font, mono_font). Never raises — a missing font file
    degrades to a standard PDF base font rather than failing the export.
    """
    global _fonts_registered
    body, mono = "Helvetica", "Courier"

    if _fonts_registered:
        return ("GeneralSans", "SometypeMono") if _fonts_registered else (body, mono)

    try:
        gs = FONT_DIR / "GeneralSans-Regular.ttf"
        gsb = FONT_DIR / "GeneralSans-Semibold.ttf"
        sm = FONT_DIR / "SometypeMono-Regular.ttf"
        if gs.exists() and sm.exists():
            pdfmetrics.registerFont(TTFont("GeneralSans", str(gs)))
            pdfmetrics.registerFont(TTFont("SometypeMono", str(sm)))
            if gsb.exists():
                pdfmetrics.registerFont(TTFont("GeneralSans-Bold", str(gsb)))
            _fonts_registered = True
            return "GeneralSans", "SometypeMono"
    except Exception:
        pass

    return body, mono


def styles() -> dict[str, ParagraphStyle]:
    body_font, mono_font = register_fonts()
    bold_font = "GeneralSans-Bold" if body_font == "GeneralSans" else "Helvetica-Bold"
    base = getSampleStyleSheet()

    return {
        "title": ParagraphStyle(
            "title", parent=base["Title"], fontName=bold_font, fontSize=26,
            leading=30, textColor=INK, spaceAfter=4 * mm, alignment=TA_LEFT,
        ),
        "subtitle": ParagraphStyle(
            "subtitle", fontName=body_font, fontSize=12, leading=16,
            textColor=MUTED, spaceAfter=8 * mm,
        ),
        "h1": ParagraphStyle(
            "h1", fontName=bold_font, fontSize=15, leading=19,
            textColor=INK, spaceBefore=8 * mm, spaceAfter=3 * mm,
        ),
        "h2": ParagraphStyle(
            "h2", fontName=bold_font, fontSize=11.5, leading=15,
            textColor=INK, spaceBefore=5 * mm, spaceAfter=2 * mm,
        ),
        "body": ParagraphStyle(
            "body", fontName=body_font, fontSize=9.5, leading=13.5,
            textColor=INK, spaceAfter=2.5 * mm,
        ),
        "small": ParagraphStyle(
            "small", fontName=body_font, fontSize=8, leading=11, textColor=MUTED,
        ),
        "mono": ParagraphStyle(
            "mono", fontName=mono_font, fontSize=7.5, leading=10, textColor=MUTED,
        ),
        "citation": ParagraphStyle(
            "citation", fontName=mono_font, fontSize=7.5, leading=11,
            textColor=INK, leftIndent=4 * mm,
        ),
    }


def risk_color(score: float | None) -> colors.Color:
    """Three states only. Red should be rare enough to mean something."""
    if score is None:
        return MUTED
    if score >= 70:
        return RISK_HIGH
    if score >= 40:
        return RISK_MED
    return RISK_LOW


def hrule(width: float = 170 * mm) -> Table:
    t = Table([[""]], colWidths=[width], rowHeights=[0.4])
    t.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.5, RULE)]))
    return t


def kv_table(rows: list[tuple[str, str]], width: float = 170 * mm) -> Table:
    """Label/value table. Used for register fields and score decomposition."""
    st = styles()
    data = [
        [Paragraph(f"<b>{k}</b>", st["small"]), Paragraph(str(v or "—"), st["body"])]
        for k, v in rows
    ]
    t = Table(data, colWidths=[width * 0.34, width * 0.66])
    t.setStyle(
        TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 1.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
            ("LINEBELOW", (0, 0), (-1, -2), 0.25, RULE),
        ])
    )
    return t


def dimension_table(dimensions: list[dict], width: float = 170 * mm) -> Table:
    """
    Score decomposition — raw, baseline and z-score as SEPARATE columns.

    Collapsing them into one number is precisely what made the original engine
    look like a black box. The reader should be able to see that a score is
    high because it deviates from THIS vendor's norm, not because the vendor
    is large.
    """
    st = styles()
    header = ["Dimension", "Value", "Baseline", "z", "Anomaly", "Weight", "Confidence"]
    data = [[Paragraph(f"<b>{h}</b>", st["small"]) for h in header]]

    for d in dimensions:
        tier = str(d.get("confidence", "unconfirmed")).lower()
        data.append([
            Paragraph(str(d.get("dimension", "—")).replace("_", " "), st["small"]),
            Paragraph(_num(d.get("raw_value")), st["mono"]),
            Paragraph(_num(d.get("baseline")), st["mono"]),
            Paragraph(_num(d.get("z_score"), 2), st["mono"]),
            Paragraph(_num(d.get("anomaly_ratio"), 2), st["mono"]),
            Paragraph(_num(d.get("weight_applied"), 2), st["mono"]),
            Paragraph(
                f'<font color="{TIER_COLORS.get(tier, MUTED).hexval()[2:]}">{tier}</font>',
                st["small"],
            ),
        ])

    t = Table(data, colWidths=[width * x for x in (0.24, 0.12, 0.13, 0.10, 0.13, 0.12, 0.16)])
    t.setStyle(
        TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LINEBELOW", (0, 0), (-1, 0), 0.6, INK),
            ("LINEBELOW", (0, 1), (-1, -2), 0.25, RULE),
            ("TOPPADDING", (0, 0), (-1, -1), 2.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
        ])
    )
    return t


def citation_block(citations: list[dict], width: float = 170 * mm) -> list:
    """
    Numbered sources with BOTH the live URL and the Wayback archive URL.

    The archive link is not a nicety. Cited news URLs 404 within a year, and an
    evidence pack whose sources have evaporated is not evidence.
    """
    st = styles()
    out = [Paragraph("Sources", st["h2"])]

    if not citations:
        out.append(Paragraph("No sources recorded for this section.", st["small"]))
        return out

    for c in sorted(citations, key=lambda x: x.get("index", 0)):
        idx = c.get("index", "?")
        url = c.get("url") or "—"
        archive = c.get("archive_url")
        tier = str(c.get("confidence", "")).lower()

        line = f"[{idx}] {url}"
        if archive:
            line += f"<br/>&nbsp;&nbsp;&nbsp;&nbsp;archived: {archive}"
        if tier:
            line += f"  ({tier})"
        out.append(Paragraph(line, st["citation"]))

    return out


def audit_metrics_block(metrics: dict, width: float = 170 * mm) -> Table:
    """
    TWO numbers, never one.

    narrative_resolution_pct  — every citation marker resolves to a signal.
    extraction_fidelity_pct   — the stored excerpt actually supports the claim.

    The original conflated marker count with claim count and only ever proved
    the first. Reporting both, separately, is the honest version.
    """
    st = styles()
    rows = [
        ["Metric", "Value", "Basis"],
        [
            "Citation resolution",
            _pct(metrics.get("narrative_resolution_pct")),
            f"{metrics.get('distinct_citations', 0)} distinct citations, "
            f"{metrics.get('distinct_claims', 0)} distinct claims, "
            f"{metrics.get('unresolved_count', 0)} unresolved",
        ],
        [
            "Extraction fidelity",
            _pct(metrics.get("extraction_fidelity_pct")),
            f"{metrics.get('entailment_sampled', 0)} sampled, "
            f"{metrics.get('entailment_failed', 0)} failed entailment",
        ],
    ]
    data = [[Paragraph(f"<b>{c}</b>" if i == 0 else str(c), st["small"]) for c in r]
            for i, r in enumerate(rows)]
    t = Table(data, colWidths=[width * 0.26, width * 0.14, width * 0.60])
    t.setStyle(
        TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LINEBELOW", (0, 0), (-1, 0), 0.6, INK),
            ("LINEBELOW", (0, 1), (-1, -2), 0.25, RULE),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ])
    )
    return t


def _num(v, places: int = 1) -> str:
    if v is None:
        return "—"
    try:
        return f"{float(v):.{places}f}"
    except (TypeError, ValueError):
        return str(v)


def _pct(v) -> str:
    return "not measured" if v is None else f"{float(v):.1f}%"


def spacer(h: float = 4) -> Spacer:
    return Spacer(1, h * mm)