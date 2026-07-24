"""
Immutable render store — RETRIEVE, NEVER RE-RUN.

The single most important rule in this domain: once an export is rendered, it
is frozen. An auditor asking "show me the March register" gets the bytes that
were issued in March, not a fresh render of March's data.

Why this matters beyond pedantry:
  - Narrative artifacts are LLM output. Re-running a non-deterministic model
    produces a different document, and an auditor comparing the two rightly
    concludes the trail is broken.
  - The chain head hash printed on an export is a point-in-time claim. Re-render
    it later and the hash differs, which looks like tampering.

Side effect that pays for itself: this is also the fix for the original's
130-second cold PDF export. Unchanged vendors are a lookup, not a regeneration.

Storage: bytes on disk under EXPORT_STORE_DIR, keyed by content hash. A row in
`export_artifacts` records the metadata. In production this directory should be
object storage; the interface is the same.
"""

from __future__ import annotations

import hashlib
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import REPO_ROOT
from db.models.export_artifact import ExportArtifact, ExportFormat, ExportKind

EXPORT_STORE_DIR = Path(
    os.environ.get("EXPORT_STORE_DIR", REPO_ROOT / "var" / "exports")
)


@dataclass
class StoredArtifact:
    id: uuid.UUID
    content_hash: str
    kind: ExportKind
    fmt: ExportFormat
    filename: str
    size_bytes: int
    generated_at: datetime
    chain_head_hash: str
    from_cache: bool

    @property
    def path(self) -> Path:
        return artifact_path(self.content_hash, self.fmt)


def artifact_path(content_hash: str, fmt: ExportFormat) -> Path:
    """Sharded by hash prefix — a flat directory of 10k exports is unpleasant."""
    ext = {"pdf": "pdf", "its_csv": "zip", "its_json": "json"}[fmt.value]
    return EXPORT_STORE_DIR / content_hash[:2] / f"{content_hash}.{ext}"


def compute_content_hash(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def compute_input_hash(inputs: dict) -> str:
    """
    Hash of everything that determined this export's content.

    Two exports with the same input hash MUST have the same bytes. If they
    don't, something non-deterministic leaked into the renderer — which is
    exactly what artifact_immutable_test.py checks for.

    Deliberately includes the chain head: the same register data with a
    different chain head is a different document, because the head is printed
    on the cover.
    """
    import json

    canonical = json.dumps(inputs, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


async def find_existing(
    session: AsyncSession, org_id: uuid.UUID, input_hash: str
) -> ExportArtifact | None:
    """Cache lookup. The whole performance story lives here."""
    return (
        await session.execute(
            select(ExportArtifact)
            .where(
                ExportArtifact.org_id == org_id,
                ExportArtifact.input_hash == input_hash,
                ExportArtifact.superseded.is_(False),
            )
            .order_by(ExportArtifact.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def store(
    session: AsyncSession,
    *,
    org_id: uuid.UUID,
    vendor_id: uuid.UUID | None,
    kind: ExportKind,
    fmt: ExportFormat,
    payload: bytes,
    input_hash: str,
    chain_head_hash: str,
    filename: str,
    generated_by: str,
    detail: dict | None = None,
) -> StoredArtifact:
    """
    Persist a rendered export.

    If the identical content already exists, return the existing record rather
    than writing a duplicate. Content-addressed storage means an unchanged
    register produces zero new bytes.
    """
    content_hash = compute_content_hash(payload)

    existing = (
        await session.execute(
            select(ExportArtifact).where(ExportArtifact.content_hash == content_hash)
        )
    ).scalar_one_or_none()

    if existing is not None:
        return StoredArtifact(
            id=existing.id,
            content_hash=existing.content_hash,
            kind=existing.kind,
            fmt=existing.fmt,
            filename=existing.filename,
            size_bytes=existing.size_bytes,
            generated_at=existing.generated_at,
            chain_head_hash=existing.chain_head_hash,
            from_cache=True,
        )

    path = artifact_path(content_hash, fmt)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)

    row = ExportArtifact(
        org_id=org_id,
        vendor_id=vendor_id,
        kind=kind,
        fmt=fmt,
        content_hash=content_hash,
        input_hash=input_hash,
        chain_head_hash=chain_head_hash,
        filename=filename,
        size_bytes=len(payload),
        generated_at=datetime.now(timezone.utc),
        generated_by=generated_by,
        detail=detail or {},
    )
    session.add(row)
    await session.flush()

    return StoredArtifact(
        id=row.id,
        content_hash=content_hash,
        kind=kind,
        fmt=fmt,
        filename=filename,
        size_bytes=len(payload),
        generated_at=row.generated_at,
        chain_head_hash=chain_head_hash,
        from_cache=False,
    )


async def retrieve(
    session: AsyncSession, org_id: uuid.UUID, artifact_id: uuid.UUID
) -> tuple[ExportArtifact, bytes] | None:
    """
    THE AUDITOR'S PATH. Returns the bytes as issued.

    There is deliberately no `regenerate()` in this module. If you find
    yourself wanting one, the answer is a new artifact, not a re-render of an
    old one.
    """
    row = (
        await session.execute(
            select(ExportArtifact).where(
                ExportArtifact.id == artifact_id, ExportArtifact.org_id == org_id
            )
        )
    ).scalar_one_or_none()
    if row is None:
        return None

    path = artifact_path(row.content_hash, row.fmt)
    if not path.exists():
        return None

    payload = path.read_bytes()

    # An artifact whose bytes no longer hash to their recorded value has been
    # tampered with on disk. Refuse to serve it rather than serve it silently.
    if compute_content_hash(payload) != row.content_hash:
        raise RuntimeError(
            f"Artifact {artifact_id} failed integrity check — stored bytes do "
            f"not match recorded content_hash. Do not trust this file."
        )

    return row, payload


async def list_artifacts(
    session: AsyncSession,
    org_id: uuid.UUID,
    kind: ExportKind | None = None,
    limit: int = 50,
) -> list[ExportArtifact]:
    stmt = (
        select(ExportArtifact)
        .where(ExportArtifact.org_id == org_id)
        .order_by(ExportArtifact.generated_at.desc())
        .limit(limit)
    )
    if kind:
        stmt = stmt.where(ExportArtifact.kind == kind)
    return list((await session.execute(stmt)).scalars())