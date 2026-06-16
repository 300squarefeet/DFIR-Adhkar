"""Phase 8 (RAG): case_embeddings table.

Revision ID: 0013
Revises: 0012
Create Date: 2026-06-17
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "case_embeddings",
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
                "organizations.id", name="fk_case_embeddings_organization_id_organizations"
            ),
            nullable=False,
        ),
        sa.Column(
            "case_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cases.id", name="fk_case_embeddings_case_id_cases"),
            nullable=False,
            unique=True,
        ),
        sa.Column("model_name", sa.String(100), nullable=False),
        sa.Column("dimension", sa.Integer, nullable=False),
        sa.Column("embedding_text", sa.String, nullable=False),
        sa.Column("source_excerpt", sa.String, nullable=False, server_default=""),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_case_embeddings_organization_id", "case_embeddings", ["organization_id"])
    op.create_index("ix_case_embeddings_case_id", "case_embeddings", ["case_id"])


def downgrade() -> None:
    op.drop_index("ix_case_embeddings_case_id", table_name="case_embeddings")
    op.drop_index("ix_case_embeddings_organization_id", table_name="case_embeddings")
    op.drop_table("case_embeddings")
