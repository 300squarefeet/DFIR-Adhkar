"""Phase 9: attachments + case_shares.

Revision ID: 0012
Revises: 0011
Create Date: 2026-06-17
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "attachments",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", name="fk_attachments_organization_id_organizations"),
            nullable=False,
        ),
        sa.Column(
            "case_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cases.id", name="fk_attachments_case_id_cases"),
            nullable=True,
        ),
        sa.Column(
            "task_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tasks.id", name="fk_attachments_task_id_tasks"),
            nullable=True,
        ),
        sa.Column("filename", sa.String(500), nullable=False),
        sa.Column("content_type", sa.String(200), nullable=False),
        sa.Column("size_bytes", sa.Integer, nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("storage_key", sa.String(500), nullable=False),
        sa.Column("is_quarantined", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("av_scan_status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column(
            "uploaded_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", name="fk_attachments_uploaded_by_users"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_attachments_organization_id", "attachments", ["organization_id"])
    op.create_index("ix_attachments_case_id", "attachments", ["case_id"])
    op.create_index("ix_attachments_task_id", "attachments", ["task_id"])
    op.create_index("ix_attachments_sha256", "attachments", ["sha256"])

    op.create_table(
        "case_shares",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", name="fk_case_shares_organization_id_organizations"),
            nullable=False,
        ),
        sa.Column(
            "case_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cases.id", name="fk_case_shares_case_id_cases"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", name="fk_case_shares_user_id_users"),
            nullable=False,
        ),
        sa.Column("can_comment", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("can_upload", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "granted_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", name="fk_case_shares_granted_by_users"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("case_id", "user_id", name="uq_case_shares_case_user"),
    )
    op.create_index("ix_case_shares_organization_id", "case_shares", ["organization_id"])
    op.create_index("ix_case_shares_case_id", "case_shares", ["case_id"])


def downgrade() -> None:
    op.drop_index("ix_case_shares_case_id", table_name="case_shares")
    op.drop_index("ix_case_shares_organization_id", table_name="case_shares")
    op.drop_table("case_shares")
    op.drop_index("ix_attachments_sha256", table_name="attachments")
    op.drop_index("ix_attachments_task_id", table_name="attachments")
    op.drop_index("ix_attachments_case_id", table_name="attachments")
    op.drop_index("ix_attachments_organization_id", table_name="attachments")
    op.drop_table("attachments")
