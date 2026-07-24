"""
The ITS export must pass its own validation rules, and the validator must
catch the errors it claims to catch.

A validator that never fails is not a validator.
"""

from __future__ import annotations

import io
import json
import uuid
import zipfile
from datetime import date, datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy import create_engine, text

from backend.config import settings
from db.models.contract import Contract, SubstitutabilityRating
from db.models.org import Org
from db.models.vendor import EntityType, Vendor
from db.session import SessionFactory
from reporting.its_export.templates import ALL_TEMPLATES, coverage_summary
from reporting.its_export.validator import Severity, lei_checksum_valid, validate_export
from reporting.its_export.writer import build_tables, write_its_register

MARKER = "ITS-TEST"

OWNER_URL = (settings.sync_database_url or settings.database_owner_url or "").replace(
    "postgresql+asyncpg://", "postgresql://"
)
owner_engine = create_engine(OWNER_URL, future=True)

pytestmark = pytest.mark.asyncio

# The vendor's LEI (Deutsche Bank AG). Real and checksum-valid — a fabricated
# one would let a broken MOD 97-10 implementation pass.
VALID_LEI = "7LTWFZYICNSX8D621K86"

# The FILING entity's LEI (Barclays Bank PLC). Deliberately different from
# VALID_LEI so that code confusing filer with provider fails this test.
FILER_LEI = "G5GSEF7VJP5I7OUK5573"


def _cleanup() -> None:
    with owner_engine.begin() as c:
        c.execute(text(f"DELETE FROM contracts WHERE contractual_arrangement_ref LIKE '{MARKER}%'"))
        c.execute(text(f"DELETE FROM vendors WHERE display_name LIKE '{MARKER}%'"))
        c.execute(text(f"DELETE FROM orgs WHERE name LIKE '{MARKER}%'"))


@pytest_asyncio.fixture
async def seeded():
    _cleanup()
    async with SessionFactory() as s:
        org = Org(
            clerk_org_id=f"{MARKER}-{uuid.uuid4().hex[:8]}",
            name=f"{MARKER} Bank",
            home_country="IE",
            lei=FILER_LEI,
            entity_type="credit_institution",
        )
        s.add(org)
        await s.flush()

        v = Vendor(
            lei=VALID_LEI,
            legal_name=f"{MARKER} Cloud Services Ltd",
            display_name=f"{MARKER} Cloud",
            entity_type=EntityType.PUBLIC_US,
            org_id=org.id,
        )
        s.add(v)
        await s.flush()

        s.add(
            Contract(
                vendor_id=v.id,
                org_id=org.id,
                contractual_arrangement_ref=f"{MARKER}-CA-001",
                provider_lei=VALID_LEI,
                provider_legal_name=f"{MARKER} Cloud Services Ltd",
                provider_country="IE",
                function_identifier="F-01",
                function_name="Core banking hosting",
                ict_service_type="cloud infrastructure",
                supports_critical_function=True,
                start_date=date(2025, 1, 1),
                end_date=date(2027, 12, 31),
                notice_period_days=90,
                governing_law_country="IE",
                annual_cost_eur=250000,
                data_location_countries=["IE", "DE"],
                processing_location_countries=["IE"],
                sensitive_data_involved=True,
                subcontractors=[
                    {"name": "SubCo A", "lei": VALID_LEI, "rank": 1, "country": "DE"}
                ],
                substitutability=SubstitutabilityRating.HIGHLY_COMPLEX,
                exit_plan_exists=True,
                exit_plan_last_tested=date(2026, 3, 1),
                reintegration_possible=True,
            )
        )
        await s.commit()
        oid = org.id
    yield oid
    _cleanup()


async def test_lei_checksum_rejects_invalid():
    """A regex-shaped LEI with wrong check digits must be rejected."""
    assert lei_checksum_valid(VALID_LEI)
    assert not lei_checksum_valid("7LTWFZYICNSX8D621K99")   # bad check digits
    assert not lei_checksum_valid("TOOSHORT")
    assert not lei_checksum_valid("7ltwfzyicnsx8d621k86")   # lowercase


async def test_export_passes_own_validation(seeded):
    async with SessionFactory() as s:
        tables, _ = await build_tables(s, seeded)
        report = validate_export(tables)

    # Mandatory fields Troy does not source (org LEI, competent authority)
    # produce WARNINGS, not errors — they must be supplied by the filer.
    hard = [
        f for f in report.errors
        if "not sourced from Troy" not in f.message
    ]
    assert not hard, [f.as_dict() for f in hard]


async def test_validator_catches_bad_lei(seeded):
    async with SessionFactory() as s:
        tables, _ = await build_tables(s, seeded)

    tables["RT.05.01"][0]["b_05.01.0010"] = "NOTAVALIDLEIVALUE123"
    report = validate_export(tables)
    assert any("check-digit" in f.message or "LEI format" in f.message for f in report.errors)


async def test_validator_catches_date_inversion(seeded):
    async with SessionFactory() as s:
        tables, _ = await build_tables(s, seeded)

    tables["RT.02.02"][0]["b_02.02.0070"] = "2027-01-01"
    tables["RT.02.02"][0]["b_02.02.0080"] = "2025-01-01"
    report = validate_export(tables)
    assert any("precedes start date" in f.message for f in report.errors)


async def test_validator_catches_orphan_reference(seeded):
    async with SessionFactory() as s:
        tables, _ = await build_tables(s, seeded)

    tables["RT.02.02"][0]["b_02.02.0010"] = "GHOST-REF-999"
    report = validate_export(tables)
    assert any("does not appear in RT.02.01" in f.message for f in report.errors)


async def test_zip_contains_every_template(seeded):
    async with SessionFactory() as s:
        payload = await write_its_register(s, seeded, fmt="csv")

    with zipfile.ZipFile(io.BytesIO(payload)) as z:
        names = set(z.namelist())
        for tpl in ALL_TEMPLATES:
            assert f"{tpl.code}.csv" in names
            assert f"labels/{tpl.code}.labels.csv" in names
        assert "manifest.json" in names
        assert "README.txt" in names


async def test_manifest_states_its_own_limits(seeded):
    """
    The manifest must declare what it does NOT cover. Shipping a partial
    register that reads as complete is the overclaim this project exists to
    avoid.
    """
    async with SessionFactory() as s:
        payload = await write_its_register(s, seeded, fmt="csv")

    with zipfile.ZipFile(io.BytesIO(payload)) as z:
        manifest = json.loads(z.read("manifest.json"))

    assert manifest["scope"]["templates_not_implemented"]
    assert "not a complete register submission" in manifest["scope"]["statement"]
    assert "does not guarantee acceptance" in manifest["validation"]["scope_note"]
    assert len(manifest["evidence_chain_head"]) == 64


async def test_json_export_parses(seeded):
    async with SessionFactory() as s:
        payload = await write_its_register(s, seeded, fmt="json")
    data = json.loads(payload)
    assert "manifest" in data and "tables" in data
    assert data["tables"]["RT.02.01"]


async def test_coverage_summary_is_honest():
    c = coverage_summary()
    assert c["fields_requiring_manual_entry"] > 0, (
        "If every field were sourced from Troy the coverage claim would be "
        "false — several ITS fields have no source in this system."
    )