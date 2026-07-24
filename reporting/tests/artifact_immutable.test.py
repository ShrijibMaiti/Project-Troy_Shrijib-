"""
Re-export must return the byte-identical prior artifact.

This is the test that protects the whole audit story. If rendering the same
inputs twice produces different bytes, then "reproduction is retrieval" is
false and an auditor comparing two copies of the March report would find them
different.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy import create_engine, select, text

from backend.config import settings
from db.models.export_artifact import ExportFormat, ExportKind
from db.models.org import Org
from db.models.vendor import EntityType, Vendor
from db.session import SessionFactory
from reporting import artifacts as art

MARKER = "ART-TEST"

OWNER_URL = (settings.sync_database_url or settings.database_owner_url or "").replace(
    "postgresql+asyncpg://", "postgresql://"
)
owner_engine = create_engine(OWNER_URL, future=True)

pytestmark = pytest.mark.asyncio


def _cleanup() -> None:
    with owner_engine.begin() as c:
        c.execute(text("ALTER TABLE export_artifacts DISABLE TRIGGER trg_export_artifacts_no_delete"))
        c.execute(text(f"DELETE FROM export_artifacts WHERE filename LIKE '{MARKER}%'"))
        c.execute(text("ALTER TABLE export_artifacts ENABLE TRIGGER trg_export_artifacts_no_delete"))
        c.execute(text(f"DELETE FROM vendors WHERE display_name LIKE '{MARKER}%'"))
        c.execute(text(f"DELETE FROM orgs WHERE name LIKE '{MARKER}%'"))


@pytest_asyncio.fixture
async def org_id():
    _cleanup()
    async with SessionFactory() as s:
        org = Org(
            clerk_org_id=f"{MARKER}-{uuid.uuid4().hex[:8]}",
            name=f"{MARKER} Bank",
            home_country="IE",
        )
        s.add(org)
        await s.commit()
        oid = org.id
    yield oid
    _cleanup()


async def test_identical_content_is_stored_once(org_id):
    payload = b"%PDF-1.4 identical bytes for both calls"

    async with SessionFactory() as s:
        a = await art.store(
            s, org_id=org_id, vendor_id=None,
            kind=ExportKind.EVIDENCE_PACK, fmt=ExportFormat.PDF,
            payload=payload, input_hash="a" * 64, chain_head_hash="b" * 64,
            filename=f"{MARKER}-1.pdf", generated_by="test",
        )
        await s.commit()

    async with SessionFactory() as s:
        b = await art.store(
            s, org_id=org_id, vendor_id=None,
            kind=ExportKind.EVIDENCE_PACK, fmt=ExportFormat.PDF,
            payload=payload, input_hash="a" * 64, chain_head_hash="b" * 64,
            filename=f"{MARKER}-2.pdf", generated_by="test",
        )
        await s.commit()

    assert b.from_cache is True
    assert a.id == b.id
    assert a.content_hash == b.content_hash


async def test_retrieve_returns_exact_bytes(org_id):
    payload = b"%PDF-1.4 " + bytes(range(256)) * 4

    async with SessionFactory() as s:
        stored = await art.store(
            s, org_id=org_id, vendor_id=None,
            kind=ExportKind.EVIDENCE_PACK, fmt=ExportFormat.PDF,
            payload=payload, input_hash="c" * 64, chain_head_hash="d" * 64,
            filename=f"{MARKER}-exact.pdf", generated_by="test",
        )
        await s.commit()
        aid = stored.id

    async with SessionFactory() as s:
        row, got = await art.retrieve(s, org_id, aid)

    assert got == payload, "retrieved bytes differ from stored bytes"
    assert row.content_hash == art.compute_content_hash(payload)


async def test_find_existing_matches_on_input_hash(org_id):
    async with SessionFactory() as s:
        await art.store(
            s, org_id=org_id, vendor_id=None,
            kind=ExportKind.ITS_REGISTER, fmt=ExportFormat.ITS_CSV,
            payload=b"zipbytes", input_hash="e" * 64, chain_head_hash="f" * 64,
            filename=f"{MARKER}-reg.zip", generated_by="test",
        )
        await s.commit()

    async with SessionFactory() as s:
        found = await art.find_existing(s, org_id, "e" * 64)
        assert found is not None
        missing = await art.find_existing(s, org_id, "0" * 64)
        assert missing is None


async def test_tampered_file_is_refused(org_id):
    """
    An artifact whose bytes no longer hash to their recorded value must not be
    served. Serving it silently would mean handing an auditor a document we
    have already proven we cannot vouch for.
    """
    payload = b"%PDF-1.4 original"

    async with SessionFactory() as s:
        stored = await art.store(
            s, org_id=org_id, vendor_id=None,
            kind=ExportKind.EVIDENCE_PACK, fmt=ExportFormat.PDF,
            payload=payload, input_hash="1" * 64, chain_head_hash="2" * 64,
            filename=f"{MARKER}-tamper.pdf", generated_by="test",
        )
        await s.commit()
        aid, path = stored.id, stored.path

    path.write_bytes(b"%PDF-1.4 TAMPERED")

    async with SessionFactory() as s:
        with pytest.raises(RuntimeError, match="integrity check"):
            await art.retrieve(s, org_id, aid)


async def test_artifact_row_is_immutable(org_id):
    """content_hash cannot be edited — enforced by trigger, not convention."""
    async with SessionFactory() as s:
        stored = await art.store(
            s, org_id=org_id, vendor_id=None,
            kind=ExportKind.EVIDENCE_PACK, fmt=ExportFormat.PDF,
            payload=b"%PDF-1.4 immutable", input_hash="3" * 64,
            chain_head_hash="4" * 64, filename=f"{MARKER}-immut.pdf",
            generated_by="test",
        )
        await s.commit()
        aid = stored.id

    blocked = False
    try:
        with owner_engine.begin() as c:
            c.execute(
                text("UPDATE export_artifacts SET content_hash = :h WHERE id = :i"),
                {"h": "9" * 64, "i": str(aid)},
            )
    except Exception as exc:
        blocked = "immutable" in str(exc).lower()

    assert blocked, "export_artifacts.content_hash was editable — trigger missing"


async def test_supersede_is_permitted(org_id):
    """The one field that may change."""
    async with SessionFactory() as s:
        stored = await art.store(
            s, org_id=org_id, vendor_id=None,
            kind=ExportKind.EVIDENCE_PACK, fmt=ExportFormat.PDF,
            payload=b"%PDF-1.4 supersedable", input_hash="5" * 64,
            chain_head_hash="6" * 64, filename=f"{MARKER}-sup.pdf",
            generated_by="test",
        )
        await s.commit()
        aid = stored.id

    with owner_engine.begin() as c:
        c.execute(
            text("UPDATE export_artifacts SET superseded = true WHERE id = :i"),
            {"i": str(aid)},
        )

    async with SessionFactory() as s:
        from db.models.export_artifact import ExportArtifact

        row = (
            await s.execute(select(ExportArtifact).where(ExportArtifact.id == aid))
        ).scalar_one()
        assert row.superseded is True