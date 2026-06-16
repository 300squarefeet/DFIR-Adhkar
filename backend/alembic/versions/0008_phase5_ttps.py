"""Phase 5: TTP catalog + case_ttps (MITRE ATT&CK).

Revision ID: 0008
Revises: 0007
Create Date: 2026-06-17
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ttp_catalog",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("technique_id", sa.String(20), nullable=False, unique=True),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("tactic", sa.String(80), nullable=False),
        sa.Column("description", sa.String, nullable=True),
        sa.Column("url", sa.String(500), nullable=True),
        sa.Column("is_subtechnique", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_ttp_catalog_technique_id", "ttp_catalog", ["technique_id"])
    op.create_index("ix_ttp_catalog_tactic", "ttp_catalog", ["tactic"])

    op.create_table(
        "case_ttps",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", name="fk_case_ttps_organization_id_organizations"),
            nullable=False,
        ),
        sa.Column(
            "case_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cases.id", name="fk_case_ttps_case_id_cases"),
            nullable=False,
        ),
        sa.Column("technique_id", sa.String(20), nullable=False),
        sa.Column("tactic", sa.String(80), nullable=False),
        sa.Column("occurrence_date", sa.Date(), nullable=True),
        sa.Column("procedure_note", sa.String, nullable=True),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", name="fk_case_ttps_created_by_users"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("case_id", "technique_id", name="uq_case_ttps_case_technique"),
    )
    op.create_index("ix_case_ttps_organization_id", "case_ttps", ["organization_id"])
    op.create_index("ix_case_ttps_case_id", "case_ttps", ["case_id"])
    op.create_index("ix_case_ttps_technique_id", "case_ttps", ["technique_id"])


def downgrade() -> None:
    op.drop_index("ix_case_ttps_technique_id", table_name="case_ttps")
    op.drop_index("ix_case_ttps_case_id", table_name="case_ttps")
    op.drop_index("ix_case_ttps_organization_id", table_name="case_ttps")
    op.drop_table("case_ttps")
    op.drop_index("ix_ttp_catalog_tactic", table_name="ttp_catalog")
    op.drop_index("ix_ttp_catalog_technique_id", table_name="ttp_catalog")
    op.drop_table("ttp_catalog")
