"""Grant privileges on the crypto-shredding tables.

These two tables were added after 0002 was written, so troy_app has no
access to them at all.

Privilege shape is deliberate and asymmetric:

  shredded_fields — SELECT, INSERT only. Ciphertext is evidence: it is
      written once and never edited. Erasure works by destroying the key,
      NOT by touching the ciphertext, so the app never needs UPDATE here.

  subject_keys — SELECT, INSERT, UPDATE. UPDATE is required and is the one
      place the app is allowed to mutate: erase_subject() zeroes wrapped_key
      and sets erased_at. That single UPDATE is the GDPR Article 17
      mechanism. DELETE stays revoked so an erasure always leaves a
      tombstone row proving the request was honoured.

Revision ID: 0003_crypto_shred_grants
Revises: 0002_append_only
"""
from __future__ import annotations

from alembic import op

revision = "0003_crypto_shred_grants"
down_revision = "0002_append_only"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Ciphertext is append-only evidence.
    op.execute("REVOKE ALL ON TABLE shredded_fields FROM troy_app")
    op.execute("GRANT SELECT, INSERT ON TABLE shredded_fields TO troy_app")

    # Key rows are mutable only so erasure can zero them.
    op.execute("REVOKE ALL ON TABLE subject_keys FROM troy_app")
    op.execute("GRANT SELECT, INSERT, UPDATE ON TABLE subject_keys TO troy_app")

    # Trigger enforcement on shredded_fields, matching the other
    # evidence tables. troy_forbid_mutation() already exists from 0002.
    op.execute(
        "DROP TRIGGER IF EXISTS trg_shredded_fields_append_only ON shredded_fields"
    )
    op.execute(
        """
        CREATE TRIGGER trg_shredded_fields_append_only
        BEFORE UPDATE OR DELETE ON shredded_fields
        FOR EACH ROW EXECUTE FUNCTION troy_forbid_mutation()
        """
    )

    # subject_keys gets a narrower guard: only the erasure fields may move.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION troy_subject_keys_erasure_only()
        RETURNS TRIGGER
        LANGUAGE plpgsql
        AS $fn$
        BEGIN
            IF NEW.subject_ref IS DISTINCT FROM OLD.subject_ref
            OR NEW.id          IS DISTINCT FROM OLD.id
            OR NEW.created_at  IS DISTINCT FROM OLD.created_at
            THEN
                RAISE EXCEPTION
                    'Only wrapped_key, wrap_nonce and erased_at may be '
                    'updated on subject_keys (erasure path only).'
                    USING ERRCODE = 'restrict_violation';
            END IF;

            IF OLD.erased_at IS NOT NULL
            AND NEW.erased_at IS NULL
            THEN
                RAISE EXCEPTION 'An erasure cannot be reversed.'
                    USING ERRCODE = 'restrict_violation';
            END IF;

            RETURN NEW;
        END;
        $fn$
        """
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_subject_keys_erasure_only ON subject_keys"
    )
    op.execute(
        """
        CREATE TRIGGER trg_subject_keys_erasure_only
        BEFORE UPDATE ON subject_keys
        FOR EACH ROW EXECUTE FUNCTION troy_subject_keys_erasure_only()
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_subject_keys_erasure_only ON subject_keys"
    )
    op.execute("DROP FUNCTION IF EXISTS troy_subject_keys_erasure_only()")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_shredded_fields_append_only ON shredded_fields"
    )
    op.execute("REVOKE ALL ON TABLE shredded_fields FROM troy_app")
    op.execute("REVOKE ALL ON TABLE subject_keys FROM troy_app")