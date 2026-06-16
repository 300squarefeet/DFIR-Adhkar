"""Phase 3c: case_pages (per-case wiki).

Revision ID: 0016
Revises: 0015
Create Date: 2026-06-17
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "case_pages",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", name="fk_case_pages_organization_id_organizations"),
            nullable=False,
        ),
        sa.Column(
            "case_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cases.id", name="fk_case_pages_case_id_cases"),
            nullable=False,
        ),
        sa.Column("slug", sa.String(200), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("content", sa.String, nullable=False, server_default=""),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", name="fk_case_pages_created_by_users"),
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
        sa.UniqueConstraint("case_id", "slug", name="uq_case_pages_case_slug"),
    )
    op.create_index("ix_case_pages_organization_id", "case_pages", ["organization_id"])
    op.create_index("ix_case_pages_case_id", "case_pages", ["case_id"])


def downgrade() -> None:
    op.drop_index("ix_case_pages_case_id", table_name="case_pages")
    op.drop_index("ix_case_pages_organization_id", table_name="case_pages")
    op.drop_table("case_pages")
