"""Phase 8: ai_calls audit log.

Revision ID: 0011
Revises: 0010
Create Date: 2026-06-17
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_calls",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", name="fk_ai_calls_organization_id_organizations"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", name="fk_ai_calls_user_id_users"),
            nullable=True,
        ),
        sa.Column(
            "case_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cases.id", name="fk_ai_calls_case_id_cases"),
            nullable=True,
        ),
        sa.Column("purpose", sa.String(50), nullable=False),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("prompt", sa.String, nullable=False),
        sa.Column("response_text", sa.String, nullable=False),
        sa.Column("input_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("extra", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_ai_calls_organization_id", "ai_calls", ["organization_id"])
    op.create_index("ix_ai_calls_case_id", "ai_calls", ["case_id"])


def downgrade() -> None:
    op.drop_index("ix_ai_calls_case_id", table_name="ai_calls")
    op.drop_index("ix_ai_calls_organization_id", table_name="ai_calls")
    op.drop_table("ai_calls")
