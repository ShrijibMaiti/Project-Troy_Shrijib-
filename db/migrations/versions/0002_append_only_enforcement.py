"""Apply append-only enforcement, currency views and chain constraints.

Runs the hand-written SQL in db/integrity/append_only.sql. Kept as a migration
so the enforcement is versioned with the schema rather than being a thing
someone remembers to run.

Revision ID: 0002_append_only
Revises: 0001_initial
"""
from __future__ import annotations

from pathlib import Path

from alembic import op

revision = "0002_append_only"
down_revision = "0001_initial"
branch_labels = None
depends_on = None

SQL_PATH = Path(__file__).resolve().parents[2] / "integrity" / "append_only.sql"


def upgrade() -> None:
    sql = SQL_PATH.read_text(encoding="utf-8")
    op.execute(sql)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS signal_timeline")
    op.execute("DROP VIEW IF EXISTS signal_current")
    for t in (
        "signals",
        "excerpts",
        "narrative_artifacts",
        "corrections",
        "audit_log",
        "vendor_scores",
        "dimension_scores",
    ):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{t}_append_only ON {t}")
    op.execute("DROP TRIGGER IF EXISTS trg_alerts_ack_only ON alerts")
    op.execute("DROP FUNCTION IF EXISTS troy_forbid_mutation()")
    op.execute("DROP FUNCTION IF EXISTS troy_alerts_ack_only()")
    op.execute("ALTER TABLE signals DROP CONSTRAINT IF EXISTS uq_signals_prev_hash")
    op.execute("ALTER TABLE signals DROP CONSTRAINT IF EXISTS uq_signals_chain_seq")