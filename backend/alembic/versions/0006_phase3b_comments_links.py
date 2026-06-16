"""Phase 3b: comments, case_links, observables.case_id.

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-17
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "comments",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", name="fk_comments_organization_id_organizations"),
            nullable=False,
        ),
        sa.Column(
            "case_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cases.id", name="fk_comments_case_id_cases"),
            nullable=False,
        ),
        sa.Column(
            "author_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", name="fk_comments_author_id_users"),
            nullable=True,
        ),
        sa.Column("content", sa.String, nullable=False),
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
    )
    op.create_index("ix_comments_organization_id", "comments", ["organization_id"])
    op.create_index("ix_comments_case_id", "comments", ["case_id"])

    op.create_table(
        "case_links",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", name="fk_case_links_organization_id_organizations"),
            nullable=False,
        ),
        sa.Column(
            "source_case_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cases.id", name="fk_case_links_source_case_id_cases"),
            nullable=False,
        ),
        sa.Column(
            "target_case_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cases.id", name="fk_case_links_target_case_id_cases"),
            nullable=False,
        ),
        sa.Column("relation", sa.String(40), nullable=False, server_default="related"),
        sa.Column("note", sa.String(1000), nullable=True),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", name="fk_case_links_created_by_users"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("source_case_id", "target_case_id", name="uq_case_links_source_target"),
        sa.CheckConstraint("source_case_id <> target_case_id", name="ck_case_links_no_self_link"),
    )
    op.create_index("ix_case_links_organization_id", "case_links", ["organization_id"])
    op.create_index("ix_case_links_source_case_id", "case_links", ["source_case_id"])
    op.create_index("ix_case_links_target_case_id", "case_links", ["target_case_id"])

    op.add_column(
        "observables",
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_observables_case_id_cases", "observables", "cases", ["case_id"], ["id"]
    )
    op.create_index("ix_observables_case_id", "observables", ["case_id"])


def downgrade() -> None:
    op.drop_index("ix_observables_case_id", table_name="observables")
    op.drop_constraint("fk_observables_case_id_cases", "observables", type_="foreignkey")
    op.drop_column("observables", "case_id")
    op.drop_index("ix_case_links_target_case_id", table_name="case_links")
    op.drop_index("ix_case_links_source_case_id", table_name="case_links")
    op.drop_index("ix_case_links_organization_id", table_name="case_links")
    op.drop_table("case_links")
    op.drop_index("ix_comments_case_id", table_name="comments")
    op.drop_index("ix_comments_organization_id", table_name="comments")
    op.drop_table("comments")
