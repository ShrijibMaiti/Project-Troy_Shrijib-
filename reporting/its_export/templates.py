"""
ESAs Implementing Technical Standards — register of information templates.

SCOPE, STATED HONESTLY: this implements a defensible SUBSET of the RT.01.01–
RT.99.01 template set, covering the templates that Troy holds data for. It is
not a complete register submission package, and the export manifest says so
explicitly.

Templates implemented:
  RT.01.01  Entity maintaining the register
  RT.01.02  List of entities within scope
  RT.02.01  Contractual arrangements — general information
  RT.02.02  Contractual arrangements — specific information
  RT.05.01  ICT third-party service providers
  RT.05.02  ICT service supply chains
  RT.06.01  Functions identification
  RT.07.01  Assessment of ICT services supporting critical functions

Not implemented (no data source in Troy): RT.01.03 branches, RT.02.03
intra-group, RT.03.* signing entities, RT.04.01 entities using the service.

Field codes follow the ITS naming (b_01.01.0010 style). Where Troy's model
does not carry a mandated field, the cell is emitted empty and the validator
reports it — silently omitting a mandatory column would produce a file that
looks complete and is not.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class Field:
    code: str                 # ITS field code, e.g. "b_01.01.0010"
    name: str                 # human label
    mandatory: bool = False
    source: str | None = None      # attribute path on the source object
    transform: Callable[[Any], Any] | None = None
    note: str = ""


@dataclass
class Template:
    code: str                 # "RT.01.01"
    name: str
    fields: list[Field]
    implemented: bool = True
    note: str = ""


def _iso_date(v):
    return v.isoformat() if v else ""


def _bool_yn(v):
    return "" if v is None else ("1" if v else "0")


def _join(v):
    return ";".join(v) if v else ""


def _enum(v):
    return v.value if hasattr(v, "value") else (v or "")


# ---------------------------------------------------------------------------
# RT.01.01 — Entity maintaining the register
# ---------------------------------------------------------------------------
RT_01_01 = Template(
    code="RT.01.01",
    name="Entity maintaining the register of information",
    fields=[
        Field("b_01.01.0010", "LEI of the entity maintaining the register",
              mandatory=True, source="org.lei",
              note="Filer-supplied configuration, set on the organisation record"),
        Field("b_01.01.0020", "Name of the entity", mandatory=True, source="org.name"),
        Field("b_01.01.0030", "Country of the entity", mandatory=True, source="org.home_country"),
        Field("b_01.01.0040", "Type of entity", source="org.entity_type"),
        Field("b_01.01.0050", "Competent authority", note="Not held by Troy"),
        Field("b_01.01.0060", "Date of the reporting", mandatory=True, source="reporting_date",
              transform=_iso_date),
    ],
)

# ---------------------------------------------------------------------------
# RT.01.02 — Entities within the scope of consolidation
# ---------------------------------------------------------------------------
RT_01_02 = Template(
    code="RT.01.02",
    name="List of entities within the scope of the register",
    fields=[
        Field("b_01.02.0010", "LEI of the entity", mandatory=True, source="org.lei"),
        Field("b_01.02.0020", "Name of the entity", mandatory=True, source="org.name"),
        Field("b_01.02.0030", "Country of the entity", mandatory=True, source="org.home_country"),
        Field("b_01.02.0040", "Type of entity", source="org.entity_type"),
        Field("b_01.02.0050", "Hierarchy of the entity within the group", note="Not held by Troy"),
        Field("b_01.02.0060", "LEI of the direct parent undertaking", note="Not held by Troy"),
    ],
)

# ---------------------------------------------------------------------------
# RT.02.01 — Contractual arrangements, general
# ---------------------------------------------------------------------------
RT_02_01 = Template(
    code="RT.02.01",
    name="Contractual arrangements — general information",
    fields=[
        Field("b_02.01.0010", "Contractual arrangement reference number",
              mandatory=True, source="contract.contractual_arrangement_ref"),
        Field("b_02.01.0020", "Type of contractual arrangement",
              source="contract.ict_service_type"),
        Field("b_02.01.0030", "Overarching contractual arrangement reference",
              note="Not held by Troy"),
        Field("b_02.01.0040", "Currency of the amount reported", source="currency"),
        Field("b_02.01.0050", "Annual expense or estimated cost",
              source="contract.annual_cost_eur"),
    ],
)

# ---------------------------------------------------------------------------
# RT.02.02 — Contractual arrangements, specific
# ---------------------------------------------------------------------------
RT_02_02 = Template(
    code="RT.02.02",
    name="Contractual arrangements — specific information",
    fields=[
        Field("b_02.02.0010", "Contractual arrangement reference number",
              mandatory=True, source="contract.contractual_arrangement_ref"),
        Field("b_02.02.0020", "LEI of the financial entity making use of the service",
              mandatory=True, source="org.lei"),
        Field("b_02.02.0030", "Identification code of the ICT provider",
              mandatory=True, source="contract.provider_lei"),
        Field("b_02.02.0040", "Type of code to identify the ICT provider",
              source="provider_code_type"),
        Field("b_02.02.0050", "Function identifier", source="contract.function_identifier"),
        Field("b_02.02.0060", "Type of ICT services", source="contract.ict_service_type"),
        Field("b_02.02.0070", "Start date of the contractual arrangement",
              mandatory=True, source="contract.start_date", transform=_iso_date),
        Field("b_02.02.0080", "End date of the contractual arrangement",
              source="contract.end_date", transform=_iso_date),
        Field("b_02.02.0090", "Reason for the termination", note="Not held by Troy"),
        Field("b_02.02.0100", "Notice period for the financial entity",
              source="contract.notice_period_days"),
        Field("b_02.02.0110", "Notice period for the ICT provider", note="Not held by Troy"),
        Field("b_02.02.0120", "Country of the governing law",
              mandatory=True, source="contract.governing_law_country"),
        Field("b_02.02.0130", "Country of provision of the ICT services",
              source="contract.processing_location_countries", transform=_join),
        Field("b_02.02.0140", "Storage of data", source="contract.sensitive_data_involved",
              transform=_bool_yn),
        Field("b_02.02.0150", "Location of the data at rest",
              source="contract.data_location_countries", transform=_join),
        Field("b_02.02.0160", "Location of management of the data",
              source="contract.processing_location_countries", transform=_join),
        Field("b_02.02.0170", "Sensitiveness of the data stored",
              source="contract.sensitive_data_involved", transform=_bool_yn),
        Field("b_02.02.0180", "Reliance on the ICT service supporting a critical function",
              mandatory=True, source="contract.supports_critical_function", transform=_bool_yn),
    ],
)

# ---------------------------------------------------------------------------
# RT.05.01 — ICT third-party service providers
# ---------------------------------------------------------------------------
RT_05_01 = Template(
    code="RT.05.01",
    name="ICT third-party service providers",
    fields=[
        Field("b_05.01.0010", "Identification code of the ICT provider",
              mandatory=True, source="vendor.lei"),
        Field("b_05.01.0020", "Type of code", source="provider_code_type"),
        Field("b_05.01.0030", "Legal name of the ICT provider",
              mandatory=True, source="vendor.legal_name"),
        Field("b_05.01.0040", "Person type of the ICT provider", source="vendor.entity_type",
              transform=_enum),
        Field("b_05.01.0050", "Country of the ICT provider's headquarters",
              source="contract.provider_country"),
        Field("b_05.01.0060", "Currency of the amount reported", source="currency"),
        Field("b_05.01.0070", "Total annual expense", source="contract.annual_cost_eur"),
        Field("b_05.01.0080", "Identification code of the ICT provider's ultimate parent",
              source="vendor.ultimate_parent_lei"),
        Field("b_05.01.0090", "Type of code for the ultimate parent",
              source="parent_code_type"),
    ],
)

# ---------------------------------------------------------------------------
# RT.05.02 — ICT service supply chains
# ---------------------------------------------------------------------------
RT_05_02 = Template(
    code="RT.05.02",
    name="ICT service supply chains",
    fields=[
        Field("b_05.02.0010", "Contractual arrangement reference number",
              mandatory=True, source="contract.contractual_arrangement_ref"),
        Field("b_05.02.0020", "Type of ICT services", source="contract.ict_service_type"),
        Field("b_05.02.0030", "Identification code of the ICT provider",
              mandatory=True, source="subcontractor.lei"),
        Field("b_05.02.0040", "Type of code", source="subcontractor_code_type"),
        Field("b_05.02.0050", "Rank in the supply chain", mandatory=True,
              source="subcontractor.rank"),
        Field("b_05.02.0060", "Identification code of the recipient of the sub-service",
              source="vendor.lei"),
        Field("b_05.02.0070", "Type of code of the recipient", source="provider_code_type"),
    ],
)

# ---------------------------------------------------------------------------
# RT.06.01 — Functions
# ---------------------------------------------------------------------------
RT_06_01 = Template(
    code="RT.06.01",
    name="Functions identification",
    fields=[
        Field("b_06.01.0010", "Function identifier", mandatory=True,
              source="contract.function_identifier"),
        Field("b_06.01.0020", "LEI of the financial entity", mandatory=True, source="org.lei"),
        Field("b_06.01.0030", "Licenced activity", note="Not held by Troy"),
        Field("b_06.01.0040", "Function name", mandatory=True, source="contract.function_name"),
        Field("b_06.01.0050", "Criticality assessment",
              source="contract.supports_critical_function", transform=_bool_yn),
        Field("b_06.01.0060", "Reasons for criticality", note="Not held by Troy"),
        Field("b_06.01.0070", "Date of the last criticality assessment",
              source="contract.exit_plan_last_tested", transform=_iso_date),
        Field("b_06.01.0080", "Recovery time objective", note="Not held by Troy"),
        Field("b_06.01.0090", "Recovery point objective", note="Not held by Troy"),
        Field("b_06.01.0100", "Impact of discontinuing the function", note="Not held by Troy"),
    ],
)

# ---------------------------------------------------------------------------
# RT.07.01 — Assessment of ICT services supporting critical functions
# ---------------------------------------------------------------------------
RT_07_01 = Template(
    code="RT.07.01",
    name="Assessment of ICT services supporting critical or important functions",
    fields=[
        Field("b_07.01.0010", "Contractual arrangement reference number",
              mandatory=True, source="contract.contractual_arrangement_ref"),
        Field("b_07.01.0020", "Identification code of the ICT provider",
              mandatory=True, source="contract.provider_lei"),
        Field("b_07.01.0030", "Type of code", source="provider_code_type"),
        Field("b_07.01.0040", "Substitutability of the ICT provider",
              mandatory=True, source="contract.substitutability", transform=_enum),
        Field("b_07.01.0050", "Reason for the substitutability assessment",
              note="Not held by Troy"),
        Field("b_07.01.0060", "Date of the last audit on the ICT provider",
              note="Not held by Troy"),
        Field("b_07.01.0070", "Existence of an exit plan",
              mandatory=True, source="contract.exit_plan_exists", transform=_bool_yn),
        Field("b_07.01.0080", "Possibility of reintegration of the ICT service",
              source="contract.reintegration_possible", transform=_bool_yn),
        Field("b_07.01.0090", "Impact of discontinuing the ICT services",
              note="Not held by Troy"),
        Field("b_07.01.0100", "Alternative ICT providers identified", note="Not held by Troy"),
    ],
)

# ---------------------------------------------------------------------------
# Not implemented — declared explicitly so the manifest can list them
# ---------------------------------------------------------------------------
NOT_IMPLEMENTED = [
    Template("RT.01.03", "Branches", [], implemented=False,
             note="Troy holds no branch data"),
    Template("RT.02.03", "Intra-group contractual arrangements", [], implemented=False,
             note="Troy does not model intra-group arrangements"),
    Template("RT.03.01", "Entities signing the contractual arrangement", [],
             implemented=False, note="Troy holds no signatory data"),
    Template("RT.03.02", "ICT providers signing", [], implemented=False,
             note="Troy holds no signatory data"),
    Template("RT.03.03", "Entities providing ICT services", [], implemented=False,
             note="Covered in part by RT.05.02"),
    Template("RT.04.01", "Entities making use of the ICT services", [],
             implemented=False, note="Troy models a single using entity per org"),
]

ALL_TEMPLATES = [
    RT_01_01, RT_01_02, RT_02_01, RT_02_02,
    RT_05_01, RT_05_02, RT_06_01, RT_07_01,
]

TEMPLATES_BY_CODE = {t.code: t for t in ALL_TEMPLATES}


def mandatory_fields(template: Template) -> list[Field]:
    return [f for f in template.fields if f.mandatory]


def coverage_summary() -> dict:
    """
    Honest accounting of what this export does and does not cover. Written
    into the manifest so nobody has to take the claim on trust.
    """
    total_fields = sum(len(t.fields) for t in ALL_TEMPLATES)
    sourced = sum(1 for t in ALL_TEMPLATES for f in t.fields if f.source)
    return {
        "templates_implemented": [t.code for t in ALL_TEMPLATES],
        "templates_not_implemented": [
            {"code": t.code, "name": t.name, "reason": t.note} for t in NOT_IMPLEMENTED
        ],
        "fields_total": total_fields,
        "fields_sourced_from_troy": sourced,
        "fields_requiring_manual_entry": total_fields - sourced,
        "statement": (
            "This export covers the register templates for which Troy holds "
            "data. It is not a complete register submission. Fields marked "
            "'Not held by Troy' must be supplied by the filing entity before "
            "submission to a competent authority."
        ),
    }