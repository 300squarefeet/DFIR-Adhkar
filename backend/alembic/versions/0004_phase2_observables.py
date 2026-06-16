"""Phase 2: observables + analyzer_jobs tables.

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-17
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "observables",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", name="fk_observables_organization_id_organizations"),
            nullable=False,
        ),
        sa.Column("data_type", sa.String(50), nullable=False),
        sa.Column("data", sa.String(2000), nullable=False),
        sa.Column("tlp", sa.String(20), nullable=False, server_default="amber"),
        sa.Column("pap", sa.String(20), nullable=False, server_default="amber"),
        sa.Column("tags", postgresql.ARRAY(sa.String()), nullable=False, server_default="{}"),
        sa.Column("is_ioc", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("sighted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("ignore_similarity", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("message", sa.String(2000), nullable=True),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", name="fk_observables_created_by_users"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_observables_organization_id", "observables", ["organization_id"])
    op.create_index("ix_observables_data_type", "observables", ["data_type"])

    op.create_table(
        "analyzer_jobs",
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
                "organizations.id", name="fk_analyzer_jobs_organization_id_organizations"
            ),
            nullable=False,
        ),
        sa.Column(
            "observable_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("observables.id", name="fk_analyzer_jobs_observable_id_observables"),
            nullable=False,
        ),
        sa.Column("analyzer_name", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("report", postgresql.JSONB(), nullable=True),
        sa.Column("error_message", sa.String(2000), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", name="fk_analyzer_jobs_created_by_users"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_analyzer_jobs_organization_id", "analyzer_jobs", ["organization_id"])
    op.create_index("ix_analyzer_jobs_observable_id", "analyzer_jobs", ["observable_id"])


def downgrade() -> None:
    op.drop_index("ix_analyzer_jobs_observable_id", table_name="analyzer_jobs")
    op.drop_index("ix_analyzer_jobs_organization_id", table_name="analyzer_jobs")
    op.drop_table("analyzer_jobs")
    op.drop_index("ix_observables_data_type", table_name="observables")
    op.drop_index("ix_observables_organization_id", table_name="observables")
    op.drop_table("observables")
