"""Store enum VALUES in Postgres, not Python member NAMES.

SQLAlchemy's Enum type defaults to persisting the member NAME
(LEADERSHIP_CHANGE). Our Python enums are str-valued with lowercase values
(leadership_change), and every external contract — JSON payloads, the API,
the frontend, raw SQL filters — uses the value.

That mismatch is invisible through the ORM (it converts on read) and fatal in
raw SQL: `WHERE metric::text = 'leadership_change'` matches nothing, silently,
forever.

This renames every label to its lowercase form. Paired with values_callable
on the models, Postgres and Python then agree everywhere.

Revision ID: 0004_enum_lowercase
Revises: 0003_crypto_shred_grants
"""
from __future__ import annotations

from alembic import op

revision = "0004_enum_lowercase"
down_revision = "0003_crypto_shred_grants"
branch_labels = None
depends_on = None

ENUM_TYPES = [
    "signal_metric",
    "signal_source",
    "audit_action",
    "org_role",
    "entity_type",
    "substitutability_rating",
    "alert_severity",
    "correction_reason",
    "confidence_tier",
]


def _rename(direction: str) -> None:
    """direction: 'lower' or 'upper'."""
    fn = "lower" if direction == "lower" else "upper"
    for t in ENUM_TYPES:
        op.execute(
            f"""
            DO $$
            DECLARE lbl text;
            BEGIN
                FOR lbl IN
                    SELECT e.enumlabel
                    FROM pg_enum e
                    JOIN pg_type t ON t.oid = e.enumtypid
                    WHERE t.typname = '{t}'
                LOOP
                    IF lbl <> {fn}(lbl) THEN
                        EXECUTE format(
                            'ALTER TYPE {t} RENAME VALUE %L TO %L',
                            lbl, {fn}(lbl)
                        );
                    END IF;
                END LOOP;
            END $$;
            """
        )


def upgrade() -> None:
    _rename("lower")


def downgrade() -> None:
    _rename("upper")