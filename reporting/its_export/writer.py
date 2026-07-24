"""
Machine-readable register export.

THE POINT: regulators expect structured files in the prescribed format, not a
PDF. The original Foreshock shipped a ReportLab PDF and called it a register.
A PDF is not a submission. This produces one CSV per implemented template plus
a manifest, zipped — and a JSON variant for API consumers.

Every export carries:
  - the chain head hash, so the monitoring evidence and the register data are
    tied to the same point in time
  - the coverage statement, listing what is NOT covered
  - the validation report, including its own scope limits
"""

from __future__ import annotations

import csv
import io
import json
import uuid
import zipfile
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.integrity.hash_chain import head_hash_for_export
from db.models.contract import Contract
from db.models.org import Org
from db.models.vendor import Vendor
from reporting.its_export.templates import ALL_TEMPLATES, Field, Template, coverage_summary
from reporting.its_export.validator import validate_export

CURRENCY = "EUR"


def _resolve(source: str | None, ctx: dict) -> Any:
    """Resolve a dotted source path like 'contract.start_date' against ctx."""
    if not source:
        return None
    cur: Any = ctx
    for part in source.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            cur = getattr(cur, part, None)
        if cur is None:
            return None
    return cur


def _cell(f: Field, ctx: dict) -> str:
    v = _resolve(f.source, ctx)
    if f.transform:
        v = f.transform(v)
    if v is None:
        return ""
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    return str(v)


def _row(tpl: Template, ctx: dict) -> dict[str, str]:
    return {f.code: _cell(f, ctx) for f in tpl.fields}


async def build_tables(
    session: AsyncSession, org_id: uuid.UUID
) -> tuple[dict[str, list[dict]], dict]:
    """Build every implemented template. Returns (tables, context_meta)."""
    org = (await session.execute(select(Org).where(Org.id == org_id))).scalar_one()

    vendors = list(
        (
            await session.execute(
                select(Vendor).where(Vendor.org_id == org_id, Vendor.is_active)
            )
        ).scalars()
    )
    contracts = {
        c.vendor_id: c
        for c in (
            await session.execute(select(Contract).where(Contract.org_id == org_id))
        ).scalars()
    }

    reporting_date = date.today()
    base = {
        "org": org,
        "reporting_date": reporting_date,
        "currency": CURRENCY,
        "provider_code_type": "1",   # 1 = LEI, per the ITS code-type enumeration
        "parent_code_type": "1",
        "subcontractor_code_type": "1",
    }

    tables: dict[str, list[dict]] = {t.code: [] for t in ALL_TEMPLATES}

    # Org-level templates: one row each.
    tables["RT.01.01"].append(_row(ALL_TEMPLATES[0], base))
    tables["RT.01.02"].append(_row(ALL_TEMPLATES[1], base))

    from reporting.its_export.templates import (
        RT_02_01, RT_02_02, RT_05_01, RT_05_02, RT_06_01, RT_07_01,
    )

    for v in vendors:
        c = contracts.get(v.id)
        ctx = {**base, "vendor": v, "contract": c}

        # A vendor with no contract record cannot appear in the register — it
        # has no arrangement reference. It is reported as a gap, not silently
        # dropped: see the manifest's `vendors_without_contract`.
        if c is None:
            continue

        tables["RT.02.01"].append(_row(RT_02_01, ctx))
        tables["RT.02.02"].append(_row(RT_02_02, ctx))
        tables["RT.05.01"].append(_row(RT_05_01, ctx))
        tables["RT.06.01"].append(_row(RT_06_01, ctx))
        tables["RT.07.01"].append(_row(RT_07_01, ctx))

        for sub in (c.subcontractors or []):
            tables["RT.05.02"].append(
                _row(RT_05_02, {**ctx, "subcontractor": sub})
            )

    meta = {
        "org_name": org.name,
        "reporting_date": reporting_date.isoformat(),
        "vendors_in_scope": len(vendors),
        "vendors_with_contract": len([v for v in vendors if v.id in contracts]),
        "vendors_without_contract": [
            v.display_name for v in vendors if v.id not in contracts
        ],
    }
    return tables, meta


async def build_manifest(
    session: AsyncSession, org_id: uuid.UUID, tables: dict, meta: dict
) -> dict:
    head = await head_hash_for_export(session)
    report = validate_export(tables)

    return {
        "format": "troy-its-register/1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "evidence_chain_head": head,
        "organisation": meta["org_name"],
        "reporting_date": meta["reporting_date"],
        "row_counts": {k: len(v) for k, v in tables.items()},
        "scope": coverage_summary(),
        "gaps": {
            "vendors_in_scope": meta["vendors_in_scope"],
            "vendors_with_contract_record": meta["vendors_with_contract"],
            "vendors_omitted_no_contract": meta["vendors_without_contract"],
            "note": (
                "Vendors without a contract record cannot appear in the register "
                "because they have no contractual arrangement reference. They are "
                "monitored, but not yet registered."
            ),
        },
        "validation": report.as_dict(),
        "disclaimer": (
            "This file is generated from a monitoring system. It covers the "
            "register templates for which data is held and is not a complete "
            "submission package. The filing entity is responsible for "
            "completeness and accuracy before submission to a competent "
            "authority."
        ),
    }


async def write_its_register(
    session: AsyncSession, org_id: uuid.UUID, fmt: str = "csv"
) -> bytes:
    """
    Returns the export bytes.

    fmt="csv"  → zip containing RT.*.csv + manifest.json + README.txt
    fmt="json" → single JSON document
    """
    tables, meta = await build_tables(session, org_id)
    manifest = await build_manifest(session, org_id, tables, meta)

    if fmt == "json":
        return json.dumps(
            {"manifest": manifest, "tables": tables}, indent=2, default=str
        ).encode("utf-8")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for tpl in ALL_TEMPLATES:
            rows = tables.get(tpl.code, [])
            out = io.StringIO()
            writer = csv.DictWriter(
                out, fieldnames=[f.code for f in tpl.fields], lineterminator="\n"
            )
            writer.writeheader()
            for r in rows:
                writer.writerow(r)

            # Human-readable header row as a second file — the field codes alone
            # are unreadable to anyone who isn't holding the ITS open.
            z.writestr(f"{tpl.code}.csv", out.getvalue())
            z.writestr(
                f"labels/{tpl.code}.labels.csv",
                "code,label,mandatory,sourced\n"
                + "\n".join(
                    f'{f.code},"{f.name}",{int(f.mandatory)},{int(bool(f.source))}'
                    for f in tpl.fields
                )
                + "\n",
            )

        z.writestr("manifest.json", json.dumps(manifest, indent=2, default=str))
        z.writestr("README.txt", _readme(manifest))

    return buf.getvalue()


def _readme(manifest: dict) -> str:
    v = manifest["validation"]
    return f"""\
TROY — ICT REGISTER EXPORT
==========================

Organisation : {manifest['organisation']}
Generated    : {manifest['generated_at']}
Reporting    : {manifest['reporting_date']}

EVIDENCE CHAIN HEAD
    {manifest['evidence_chain_head']}

    This hash covers every monitoring observation recorded up to the
    generation time. Retain it to verify the evidence store independently at
    a later date.

CONTENTS
    RT.*.csv              one file per implemented register template
    labels/RT.*.labels.csv  field code to human label mapping
    manifest.json         full metadata, scope and validation report

VALIDATION
    Result   : {'PASSED' if v['ok'] else 'FAILED'}
    Errors   : {v['error_count']}
    Warnings : {v['warning_count']}

    {v['scope_note']}

SCOPE
    {manifest['scope']['statement']}

    Templates implemented     : {', '.join(manifest['scope']['templates_implemented'])}
    Templates not implemented : {', '.join(t['code'] for t in manifest['scope']['templates_not_implemented'])}

    Fields sourced from Troy  : {manifest['scope']['fields_sourced_from_troy']} of {manifest['scope']['fields_total']}
    Requiring manual entry    : {manifest['scope']['fields_requiring_manual_entry']}

GAPS
    Vendors monitored but not registered: {len(manifest['gaps']['vendors_omitted_no_contract'])}
    {', '.join(manifest['gaps']['vendors_omitted_no_contract']) or '(none)'}

DISCLAIMER
    {manifest['disclaimer']}
"""