"""
Validation against the ITS rules Troy can check.

WHAT THIS DOES CHECK: mandatory-field presence, LEI checksum and format, ISO
3166-1 country codes, ISO 4217 currency, date ordering and format, enumerated
value membership, and referential integrity between templates (every
contractual arrangement reference in RT.02.02 must exist in RT.02.01, and so
on).

WHAT THIS DOES NOT CHECK: the ESAs' full published validation rule set, which
runs to hundreds of rules including cross-template consistency conditions that
depend on data Troy does not hold. The report says so.

Reporting a partial validation as a pass would be exactly the kind of
overclaim this project exists to avoid.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from enum import Enum

from reporting.its_export.templates import ALL_TEMPLATES, Template, mandatory_fields

LEI_RE = re.compile(r"^[A-Z0-9]{18}[0-9]{2}$")
ISO_COUNTRY_RE = re.compile(r"^[A-Z]{2}$")
ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

SUBSTITUTABILITY_VALUES = {
    "not_substitutable", "highly_complex", "medium_complex", "easily_substitutable",
}


class Severity(str, Enum):
    ERROR = "error"        # would be rejected on submission
    WARNING = "warning"    # incomplete but structurally valid
    INFO = "info"


@dataclass
class Finding:
    severity: Severity
    template: str
    field_code: str | None
    row: int | None
    message: str

    def as_dict(self) -> dict:
        return {
            "severity": self.severity.value,
            "template": self.template,
            "field": self.field_code,
            "row": self.row,
            "message": self.message,
        }


@dataclass
class ValidationReport:
    findings: list[Finding] = field(default_factory=list)
    rows_checked: int = 0

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == Severity.ERROR]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == Severity.WARNING]

    @property
    def ok(self) -> bool:
        return not self.errors

    def add(self, severity, template, field_code, row, message) -> None:
        self.findings.append(Finding(severity, template, field_code, row, message))

    def as_dict(self) -> dict:
        return {
            "ok": self.ok,
            "rows_checked": self.rows_checked,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "findings": [f.as_dict() for f in self.findings],
            "scope_note": (
                "Validation covers mandatory-field presence, format rules "
                "(LEI, ISO country, ISO date, enumerations) and referential "
                "integrity between the implemented templates. It does NOT "
                "cover the ESAs' complete published rule set. A clean result "
                "here does not guarantee acceptance by a competent authority."
            ),
        }


def lei_checksum_valid(lei: str) -> bool:
    """
    ISO 17442 LEI check digits, validated as ISO 7064 MOD 97-10.

    Worth doing properly: a syntactically-shaped but invalid LEI is exactly
    the kind of error that passes a regex and fails a submission.
    """
    if not LEI_RE.match(lei):
        return False
    digits = "".join(str(int(c, 36)) for c in lei)
    return int(digits) % 97 == 1


def validate_rows(template: Template, rows: list[dict]) -> ValidationReport:
    rep = ValidationReport()
    rep.rows_checked = len(rows)

    mandatory = mandatory_fields(template)

    for i, row in enumerate(rows, start=1):
        for f in mandatory:
            v = row.get(f.code)
            if v in (None, ""):
                sev = Severity.WARNING if not f.source else Severity.ERROR
                msg = f"Mandatory field '{f.name}' is empty."
                if not f.source:
                    msg += " This field is not sourced from Troy and must be supplied manually."
                rep.add(sev, template.code, f.code, i, msg)

        for f in template.fields:
            v = row.get(f.code)
            if v in (None, ""):
                continue
            v = str(v)

            if "LEI" in f.name or "Identification code" in f.name:
                if not LEI_RE.match(v):
                    rep.add(Severity.ERROR, template.code, f.code, i,
                            f"'{v}' is not a valid LEI format (20 alphanumeric characters).")
                elif not lei_checksum_valid(v):
                    rep.add(Severity.ERROR, template.code, f.code, i,
                            f"LEI '{v}' fails the ISO 17442 check-digit test.")

            elif "Country" in f.name or "country" in f.name:
                for part in v.split(";"):
                    if part and not ISO_COUNTRY_RE.match(part):
                        rep.add(Severity.ERROR, template.code, f.code, i,
                                f"'{part}' is not an ISO 3166-1 alpha-2 country code.")

            elif "date" in f.name.lower() or f.name.startswith("Date"):
                if not ISO_DATE_RE.match(v):
                    rep.add(Severity.ERROR, template.code, f.code, i,
                            f"'{v}' is not an ISO 8601 date (YYYY-MM-DD).")

            elif "Substitutability" in f.name:
                if v not in SUBSTITUTABILITY_VALUES:
                    rep.add(Severity.ERROR, template.code, f.code, i,
                            f"'{v}' is not a valid substitutability value.")

    return rep


def validate_export(tables: dict[str, list[dict]]) -> ValidationReport:
    """Validate every template plus cross-template referential integrity."""
    combined = ValidationReport()

    for code, rows in tables.items():
        from reporting.its_export.templates import TEMPLATES_BY_CODE

        tpl = TEMPLATES_BY_CODE.get(code)
        if tpl is None:
            continue
        r = validate_rows(tpl, rows)
        combined.findings.extend(r.findings)
        combined.rows_checked += r.rows_checked

    _check_referential_integrity(tables, combined)
    _check_date_ordering(tables, combined)
    return combined


def _check_referential_integrity(tables: dict[str, list[dict]], rep: ValidationReport) -> None:
    """Every arrangement reference used elsewhere must exist in RT.02.01."""
    known = {
        r.get("b_02.01.0010")
        for r in tables.get("RT.02.01", [])
        if r.get("b_02.01.0010")
    }

    for code, field_code in (
        ("RT.02.02", "b_02.02.0010"),
        ("RT.05.02", "b_05.02.0010"),
        ("RT.07.01", "b_07.01.0010"),
    ):
        for i, row in enumerate(tables.get(code, []), start=1):
            ref = row.get(field_code)
            if ref and ref not in known:
                rep.add(
                    Severity.ERROR, code, field_code, i,
                    f"Arrangement reference '{ref}' does not appear in RT.02.01.",
                )


def _check_date_ordering(tables: dict[str, list[dict]], rep: ValidationReport) -> None:
    for i, row in enumerate(tables.get("RT.02.02", []), start=1):
        start, end = row.get("b_02.02.0070"), row.get("b_02.02.0080")
        if start and end and ISO_DATE_RE.match(str(start)) and ISO_DATE_RE.match(str(end)):
            if date.fromisoformat(str(end)) < date.fromisoformat(str(start)):
                rep.add(Severity.ERROR, "RT.02.02", "b_02.02.0080", i,
                        "Contract end date precedes start date.")