"""
End-to-end API test: vendor added → signals appended → timeline → dispute →
trust metrics → chain verify.

Runs against the REAL database. Wrik's capture/scoring modules are not
required — the test writes signals directly through the hash chain, which is
the contract those modules will use anyway.

Run:  pytest backend/tests/api_e2e_test.py -v
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, text

from backend.config import settings
from backend.main import app
from db.integrity.hash_chain import append_signal
from db.models.excerpt import Excerpt
from db.models.org import Org
from db.models.signal import Signal, SignalMetric, SignalSource
from db.models.vendor import EntityType, Vendor
from db.session import SessionFactory

MARKER = "E2E-TEST"

OWNER_URL = (settings.sync_database_url or settings.database_owner_url or "").replace(
    "postgresql+asyncpg://", "postgresql://"
)
owner_engine = create_engine(OWNER_URL, future=True)

pytestmark = pytest.mark.asyncio


def _cleanup() -> None:
    guards = [
        ("signals", "trg_signals_append_only"),
        ("excerpts", "trg_excerpts_append_only"),
        ("shredded_fields", "trg_shredded_fields_append_only"),
        ("subject_keys", "trg_subject_keys_erasure_only"),
        ("narrative_artifacts", "trg_narrative_artifacts_append_only"),
        ("corrections", "trg_corrections_append_only"),
        ("audit_log", "trg_audit_log_append_only"),
        ("vendor_scores", "trg_vendor_scores_append_only"),
        ("dimension_scores", "trg_dimension_scores_append_only"),
    ]
    with owner_engine.begin() as c:
        for t, trg in guards:
            c.execute(text(f"ALTER TABLE {t} DISABLE TRIGGER {trg}"))
        for sql in (
            "DELETE FROM corrections WHERE actor = 'dev'",
            f"DELETE FROM audit_log WHERE org_id IN (SELECT id FROM orgs WHERE name LIKE '{MARKER}%')",
            f"DELETE FROM dimension_scores WHERE vendor_id IN (SELECT id FROM vendors WHERE display_name LIKE '{MARKER}%')",
            f"DELETE FROM vendor_scores WHERE vendor_id IN (SELECT id FROM vendors WHERE display_name LIKE '{MARKER}%')",
            f"DELETE FROM narrative_artifacts WHERE vendor_id IN (SELECT id FROM vendors WHERE display_name LIKE '{MARKER}%')",
            f"DELETE FROM signals WHERE summary LIKE '{MARKER}%'",
            f"DELETE FROM excerpts WHERE source_title LIKE '{MARKER}%'",
            f"DELETE FROM contracts WHERE vendor_id IN (SELECT id FROM vendors WHERE display_name LIKE '{MARKER}%')",
            f"DELETE FROM vendors WHERE display_name LIKE '{MARKER}%'",
            f"DELETE FROM orgs WHERE name LIKE '{MARKER}%'",
        ):
            c.execute(text(sql))
        for t, trg in guards:
            c.execute(text(f"ALTER TABLE {t} ENABLE TRIGGER {trg}"))


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


@pytest_asyncio.fixture
async def client(org_id):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-Org-Id": str(org_id)},
    ) as c:
        yield c


async def _seed_signals(vendor_id: uuid.UUID, n: int = 3) -> list[uuid.UUID]:
    ids = []
    async with SessionFactory() as s:
        vendor = await s.get(Vendor, vendor_id)
        for i in range(1, n + 1):
            url = f"https://example.com/e2e/{vendor_id}/{i}"
            body = f"{MARKER}: excerpt {i}"
            ex = Excerpt(
                source_url=url,
                archive_url=f"https://web.archive.org/web/2026/{url}",
                source_domain="example.com",
                source_title=f"{MARKER} article",
                text=body,
                char_count=len(body),
                retrieved_at=datetime.now(timezone.utc),
                content_sha256=hashlib.sha256(body.encode()).hexdigest(),
            )
            s.add(ex)
            await s.flush()

            ev = date.today() - timedelta(days=n - i)
            metric = [
                SignalMetric.LEADERSHIP_CHANGE,
                SignalMetric.LEGAL_EVENT,
                SignalMetric.HEADCOUNT_CHANGE,
            ][(i - 1) % 3]
            sig = Signal(
                vendor_id=vendor.id,
                metric=metric,
                source=SignalSource.MANUAL,
                event_date=ev,
                observed_at=datetime.now(timezone.utc),
                value=float(i),
                summary=f"{MARKER} signal {i}",
                payload={"n": i},
                excerpt_id=ex.id,
                source_url=url,
                archive_url=ex.archive_url,
                validator_verdict="accepted",
                dedup_key=hashlib.sha256(
                    f"{vendor.id}|{url}|{ev}|{metric.value}".encode()
                ).hexdigest(),
            )
            await append_signal(s, sig)
            ids.append(sig.id)
        await s.commit()
    return ids


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

async def test_health_is_reachable(client):
    r = await client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["database"] is True


async def test_full_lifecycle(client):
    # 1. Create a vendor — no hardcoded list anywhere.
    r = await client.post(
        "/api/v1/vendors",
        json={
            "legal_name": f"{MARKER} Vendor Ltd",
            "display_name": f"{MARKER} Vendor",
            "entity_type": "private",
            "aliases": ["e2e"],
        },
    )
    assert r.status_code == 201, r.text
    vendor_id = uuid.UUID(r.json()["id"])

    # 2. Fleet view shows it, flagged stale (never captured).
    r = await client.get("/api/v1/vendors")
    assert r.status_code == 200
    row = next(v for v in r.json() if v["id"] == str(vendor_id))
    assert row["is_stale"] is True
    assert row["composite"] is None

    # 3. Seed signals through the real hash chain.
    signal_ids = await _seed_signals(vendor_id, 3)

    # 4. Timeline reads from signal_timeline, with excerpts joined.
    r = await client.get(f"/api/v1/signals/vendor/{vendor_id}")
    assert r.status_code == 200
    timeline = r.json()
    assert len(timeline) == 3
    assert all(not s["is_superseded"] for s in timeline)
    assert timeline[0]["excerpt_text"] is not None
    assert timeline[0]["archive_url"] is not None  # link rot handled

    # 5. Dispute — appends a supersede row, never edits.
    r = await client.post(
        f"/api/v1/signals/{signal_ids[1]}/dispute",
        json={"reason": "wrong_entity", "note": "different company"},
    )
    assert r.status_code == 200, r.text

    # 6. Same signal is now flagged superseded; the original still exists.
    r = await client.get(f"/api/v1/signals/vendor/{vendor_id}")
    flagged = [s for s in r.json() if s["is_superseded"]]
    assert len(flagged) == 1
    assert flagged[0]["id"] == str(signal_ids[1])
    assert flagged[0]["correction_reason"] == "wrong_entity"

    # 7. Double dispute is rejected.
    r = await client.post(
        f"/api/v1/signals/{signal_ids[1]}/dispute", json={"reason": "duplicate"}
    )
    assert r.status_code == 409

    # 8. Chain verifies with the seeded rows in place.
    r = await client.get("/api/v1/trust/chain-verify?force=true")
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert len(r.json()["head_hash"]) == 64

    # 9. Audit metrics return TWO fields, not one conflated number.
    r = await client.get("/api/v1/trust/audit-metrics")
    assert r.status_code == 200
    body = r.json()
    assert "narrative_resolution_pct" in body
    assert "extraction_fidelity_pct" in body

    # 10. The dispute was audit-logged.
    r = await client.get("/api/v1/trust/audit-log")
    actions = {e["action"] for e in r.json()}
    assert "signal_disputed" in actions
    assert "vendor_created" in actions


async def test_register_join(client):
    r = await client.post(
        "/api/v1/vendors",
        json={
            "legal_name": f"{MARKER} Register Ltd",
            "display_name": f"{MARKER} Register",
            "entity_type": "public_us",
        },
    )
    vendor_id = r.json()["id"]

    # Empty contract → 0% ITS completeness.
    r = await client.get("/api/v1/register")
    row = next(x for x in r.json() if x["vendor"]["id"] == vendor_id)
    assert row["contract"] is None
    assert row["completeness_pct"] == 0.0

    r = await client.put(
        f"/api/v1/register/contract/{vendor_id}",
        json={
            "contractual_arrangement_ref": "CA-001",
            "provider_legal_name": f"{MARKER} Register Ltd",
            "provider_country": "IE",
            "function_identifier": "F-01",
            "start_date": "2025-01-01",
            "governing_law_country": "IE",
            "data_location_countries": ["IE", "DE"],
            "substitutability": "highly_complex",
            "exit_plan_exists": True,
            "supports_critical_function": True,
        },
    )
    assert r.status_code == 200
    assert r.json()["register_version"] == 1

    r = await client.get("/api/v1/register")
    row = next(x for x in r.json() if x["vendor"]["id"] == vendor_id)
    assert row["completeness_pct"] > 50


async def test_methodology_states_limitations(client):
    r = await client.get("/api/v1/methodology")
    assert r.status_code == 200
    body = r.json()
    assert len(body["limitations"]) >= 4
    # The relabel must be visible in the product, not just the pitch.
    assert any("not itself a register" in l for l in body["limitations"])


async def test_no_regenerate_endpoint_exists():
    """
    Reproduction is RETRIEVAL, never re-inference. If someone adds a
    regenerate route, this fails — which is the point.

    app.routes contains both Route objects and _IncludedRouter wrappers, so
    walk it defensively rather than assuming .path exists.
    """
    def paths(routes) -> set[str]:
        found: set[str] = set()
        for r in routes:
            p = getattr(r, "path", None)
            if p:
                found.add(p)
            sub = getattr(r, "routes", None)
            if sub:
                found |= paths(sub)
        return found

    all_paths = paths(app.routes)
    assert all_paths, "no routes discovered — the walk is broken, not the app"
    offenders = [p for p in all_paths if "regenerate" in p.lower()]
    assert not offenders, f"Regeneration endpoint found: {offenders}"