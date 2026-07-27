"""Export artifact store.

Append-only: an issued document is evidence. Editing one after the fact would
break the point of having it.

Revision ID: 0006_export_artifacts
Revises: 0005_domain8
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0006_export_artifacts"
down_revision = "0005_domain8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "export_artifacts",
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("vendor_id", sa.UUID(), nullable=True),
        sa.Column(
            "kind",
            sa.Enum(
                "evidence_pack", "vendor_report", "its_register", name="export_kind"
            ),
            nullable=False,
        ),
        sa.Column(
            "fmt",
            sa.Enum("pdf", "its_csv", "its_json", name="export_format"),
            nullable=False,
        ),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column("chain_head_hash", sa.String(length=64), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("generated_by", sa.String(length=128), nullable=False),
        sa.Column("superseded", sa.Boolean(), nullable=False),
        sa.Column("register_version", sa.Integer(), nullable=True),
        sa.Column(
            "detail",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "content_hash ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_export_artifacts_content_hash_format"),
        ),
        sa.ForeignKeyConstraint(
            ["org_id"], ["orgs.id"], name=op.f("fk_export_artifacts_org_id_orgs")
        ),
        sa.ForeignKeyConstraint(
            ["vendor_id"],
            ["vendors.id"],
            name=op.f("fk_export_artifacts_vendor_id_vendors"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_export_artifacts")),
        sa.UniqueConstraint(
            "content_hash", name=op.f("uq_export_artifacts_content_hash")
        ),
    )
    op.create_index(
        "ix_export_org_kind_generated",
        "export_artifacts",
        ["org_id", "kind", "generated_at"],
    )
    op.create_index(op.f("ix_export_artifacts_org_id"), "export_artifacts", ["org_id"])
    op.create_index(
        op.f("ix_export_artifacts_vendor_id"), "export_artifacts", ["vendor_id"]
    )
    op.create_index(
        op.f("ix_export_artifacts_input_hash"), "export_artifacts", ["input_hash"]
    )
    op.create_index(
        op.f("ix_export_artifacts_generated_at"), "export_artifacts", ["generated_at"]
    )
    op.create_index(
        op.f("ix_export_artifacts_created_at"), "export_artifacts", ["created_at"]
    )

    # UPDATE is permitted only to set `superseded`. Everything else is frozen â€”
    # enforced by the trigger below, not by convention.
    op.execute("GRANT SELECT, INSERT, UPDATE ON TABLE export_artifacts TO troy_app")

    op.execute(
        """
        CREATE OR REPLACE FUNCTION troy_export_supersede_only()
        RETURNS TRIGGER LANGUAGE plpgsql AS $fn$
        BEGIN
            IF NEW.content_hash    IS DISTINCT FROM OLD.content_hash
            OR NEW.input_hash      IS DISTINCT FROM OLD.input_hash
            OR NEW.chain_head_hash IS DISTINCT FROM OLD.chain_head_hash
            OR NEW.generated_at    IS DISTINCT FROM OLD.generated_at
            OR NEW.size_bytes      IS DISTINCT FROM OLD.size_bytes
            THEN
                RAISE EXCEPTION
                    'Export artifacts are immutable. Only "superseded" may change.'
                    USING ERRCODE = 'restrict_violation';
            END IF;
            RETURN NEW;
        END;
        $fn$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_export_artifacts_supersede_only
        BEFORE UPDATE ON export_artifacts
        FOR EACH ROW EXECUTE FUNCTION troy_export_supersede_only()
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_export_artifacts_no_delete
        BEFORE DELETE ON export_artifacts
        FOR EACH ROW EXECUTE FUNCTION troy_forbid_mutation()
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_export_artifacts_no_delete ON export_artifacts"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_export_artifacts_supersede_only ON export_artifacts"
    )
    op.execute("DROP FUNCTION IF EXISTS troy_export_supersede_only()")
    op.drop_table("export_artifacts")
    for t in ("export_kind", "export_format"):
        op.execute(f"DROP TYPE IF EXISTS {t}")
