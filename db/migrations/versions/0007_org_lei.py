"""Filing entity LEI and type on orgs.

The ITS register identifies the entity maintaining it by LEI, across four
templates. Without it the export cannot pass its own mandatory-field
validation — which is exactly what reporting/tests caught.

This is filer-supplied configuration, not monitoring data.

Revision ID: 0007_org_lei
Revises: 0006_export_artifacts
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0007_org_lei"
down_revision = "0006_export_artifacts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orgs", sa.Column("lei", sa.String(length=20), nullable=True))
    op.add_column("orgs", sa.Column("entity_type", sa.String(length=64), nullable=True))
    op.create_unique_constraint("uq_orgs_lei", "orgs", ["lei"])
    op.create_check_constraint(
        "ck_orgs_org_lei_format", "orgs", "lei IS NULL OR lei ~ '^[A-Z0-9]{20}$'"
    )


def downgrade() -> None:
    op.drop_constraint("ck_orgs_org_lei_format", "orgs", type_="check")
    op.drop_constraint("uq_orgs_lei", "orgs", type_="unique")
    op.drop_column("orgs", "entity_type")
    op.drop_column("orgs", "lei")