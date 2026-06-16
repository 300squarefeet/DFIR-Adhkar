"""Phase 6 (extras): taxonomy_entries — MISP-flavored namespace:predicate=value.

Revision ID: 0017
Revises: 0016
Create Date: 2026-06-17
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "taxonomy_entries",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "organizations.id",
                name="fk_taxonomy_entries_organization_id_organizations",
            ),
            nullable=False,
        ),
        sa.Column("namespace", sa.String(100), nullable=False),
        sa.Column("predicate", sa.String(100), nullable=False),
        sa.Column("value", sa.String(200), nullable=False),
        sa.Column("description", sa.String, nullable=True),
        sa.Column("color", sa.String(20), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "organization_id",
            "namespace",
            "predicate",
            "value",
            name="uq_taxonomy_entries_org_ns_pred_val",
        ),
    )
    op.create_index("ix_taxonomy_entries_organization_id", "taxonomy_entries", ["organization_id"])
    op.create_index("ix_taxonomy_entries_namespace", "taxonomy_entries", ["namespace"])


def downgrade() -> None:
    op.drop_index("ix_taxonomy_entries_namespace", table_name="taxonomy_entries")
    op.drop_index("ix_taxonomy_entries_organization_id", table_name="taxonomy_entries")
    op.drop_table("taxonomy_entries")
