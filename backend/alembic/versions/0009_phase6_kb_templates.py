"""Phase 6: kb_pages + case_templates.

Revision ID: 0009
Revises: 0008
Create Date: 2026-06-17
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "kb_pages",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", name="fk_kb_pages_organization_id_organizations"),
            nullable=False,
        ),
        sa.Column("slug", sa.String(200), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("content", sa.String, nullable=False, server_default=""),
        sa.Column("tags", postgresql.ARRAY(sa.String()), nullable=False, server_default="{}"),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", name="fk_kb_pages_created_by_users"),
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
        sa.UniqueConstraint("organization_id", "slug", name="uq_kb_pages_org_slug"),
    )
    op.create_index("ix_kb_pages_organization_id", "kb_pages", ["organization_id"])

    op.create_table(
        "case_templates",
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
                "organizations.id", name="fk_case_templates_organization_id_organizations"
            ),
            nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("display_name", sa.String(300), nullable=False),
        sa.Column("title_prefix", sa.String(100), nullable=True),
        sa.Column("severity", sa.Integer, nullable=False, server_default="2"),
        sa.Column("tlp", sa.String(20), nullable=False, server_default="amber"),
        sa.Column("pap", sa.String(20), nullable=False, server_default="amber"),
        sa.Column("tags", postgresql.ARRAY(sa.String()), nullable=False, server_default="{}"),
        sa.Column("description", sa.String, nullable=True),
        sa.Column("summary", sa.String, nullable=True),
        sa.Column("tasks", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("custom_fields", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", name="fk_case_templates_created_by_users"),
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
        sa.UniqueConstraint("organization_id", "name", name="uq_case_templates_org_name"),
    )
    op.create_index("ix_case_templates_organization_id", "case_templates", ["organization_id"])


def downgrade() -> None:
    op.drop_index("ix_case_templates_organization_id", table_name="case_templates")
    op.drop_table("case_templates")
    op.drop_index("ix_kb_pages_organization_id", table_name="kb_pages")
    op.drop_table("kb_pages")
