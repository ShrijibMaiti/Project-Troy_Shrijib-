"""API keys, cost events, erasure requests + their grants.

Privilege shape, deliberately:
  api_keys        — SELECT/INSERT/UPDATE. UPDATE only for last_used_at and
                    revoked_at. Not evidence, so no append-only trigger.
  api_cost_events — SELECT/INSERT only, append-only. Cost data feeds pricing
                    decisions; editable cost history is useless.
  erasure_requests— SELECT/INSERT/UPDATE. The status transition
                    requested→executed is the only mutation.

Revision ID: 0005_domain8
Revises: 0004_enum_lowercase
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005_domain8"
down_revision = "0004_enum_lowercase"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "api_keys",
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("key_prefix", sa.String(length=16), nullable=False),
        sa.Column(
            "scope",
            sa.Enum("read", "write", name="api_key_scope"),
            nullable=False,
        ),
        sa.Column("rate_limit_per_minute", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("key_hash ~ '^[0-9a-f]{64}$'", name=op.f("ck_api_keys_hash_format")),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"], name=op.f("fk_api_keys_org_id_orgs")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_api_keys")),
        sa.UniqueConstraint("key_hash", name=op.f("uq_api_keys_key_hash")),
    )
    op.create_index("ix_api_keys_hash", "api_keys", ["key_hash"])
    op.create_index(op.f("ix_api_keys_org_id"), "api_keys", ["org_id"])
    op.create_index(op.f("ix_api_keys_created_at"), "api_keys", ["created_at"])

    op.create_table(
        "api_cost_events",
        sa.Column("org_id", sa.UUID(), nullable=True),
        sa.Column("vendor_id", sa.UUID(), nullable=True),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("operation", sa.String(length=64), nullable=False),
        sa.Column("model_id", sa.String(length=64), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("request_count", sa.Integer(), nullable=False),
        sa.Column("cost_usd", sa.Float(), nullable=False),
        sa.Column(
            "detail",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"], name=op.f("fk_api_cost_events_org_id_orgs")),
        sa.ForeignKeyConstraint(
            ["vendor_id"], ["vendors.id"], name=op.f("fk_api_cost_events_vendor_id_vendors")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_api_cost_events")),
    )
    op.create_index("ix_cost_vendor_created", "api_cost_events", ["vendor_id", "created_at"])
    op.create_index("ix_cost_provider_created", "api_cost_events", ["provider", "created_at"])
    op.create_index(op.f("ix_api_cost_events_created_at"), "api_cost_events", ["created_at"])
    op.create_index(op.f("ix_api_cost_events_org_id"), "api_cost_events", ["org_id"])
    op.create_index(op.f("ix_api_cost_events_vendor_id"), "api_cost_events", ["vendor_id"])

    op.create_table(
        "erasure_requests",
        sa.Column("subject_ref", sa.String(length=64), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("requested", "executed", "rejected", name="erasure_status"),
            nullable=False,
        ),
        sa.Column("requested_by", sa.String(length=128), nullable=False),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fields_affected", sa.Integer(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"], name=op.f("fk_erasure_requests_org_id_orgs")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_erasure_requests")),
    )
    op.create_index(op.f("ix_erasure_requests_subject_ref"), "erasure_requests", ["subject_ref"])
    op.create_index(op.f("ix_erasure_requests_org_id"), "erasure_requests", ["org_id"])
    op.create_index(op.f("ix_erasure_requests_created_at"), "erasure_requests", ["created_at"])

    # ---- Grants -------------------------------------------------------
    op.execute("GRANT SELECT, INSERT, UPDATE ON TABLE api_keys TO troy_app")
    op.execute("GRANT SELECT, INSERT ON TABLE api_cost_events TO troy_app")
    op.execute("GRANT SELECT, INSERT, UPDATE ON TABLE erasure_requests TO troy_app")

    # Cost history is append-only: editable costs make pricing analysis
    # worthless. troy_forbid_mutation() already exists from 0002.
    op.execute(
        """
        CREATE TRIGGER trg_api_cost_events_append_only
        BEFORE UPDATE OR DELETE ON api_cost_events
        FOR EACH ROW EXECUTE FUNCTION troy_forbid_mutation()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_api_cost_events_append_only ON api_cost_events")
    op.drop_table("erasure_requests")
    op.drop_table("api_cost_events")
    op.drop_table("api_keys")
    for t in ("api_key_scope", "erasure_status"):
        op.execute(f"DROP TYPE IF EXISTS {t}")