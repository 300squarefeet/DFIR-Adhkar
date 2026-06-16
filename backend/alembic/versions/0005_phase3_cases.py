"""Phase 3 (cases): cases, tasks, task_logs tables.

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-17
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cases",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", name="fk_cases_organization_id_organizations"),
            nullable=False,
        ),
        sa.Column("number", sa.Integer, nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.String, nullable=True),
        sa.Column("severity", sa.Integer, nullable=False, server_default="2"),
        sa.Column("tlp", sa.String(20), nullable=False, server_default="amber"),
        sa.Column("pap", sa.String(20), nullable=False, server_default="amber"),
        sa.Column("status", sa.String(50), nullable=False, server_default="Open"),
        sa.Column("stage", sa.String(20), nullable=False, server_default="open"),
        sa.Column("resolution", sa.String(2000), nullable=True),
        sa.Column("impact_summary", sa.String(2000), nullable=True),
        sa.Column(
            "assignee_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", name="fk_cases_assignee_id_users"),
            nullable=True,
        ),
        sa.Column("start_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tags", postgresql.ARRAY(sa.String()), nullable=False, server_default="{}"),
        sa.Column("custom_fields", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("flagged", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", name="fk_cases_created_by_users"),
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
        sa.UniqueConstraint("organization_id", "number", name="uq_cases_organization_id_number"),
    )
    op.create_index("ix_cases_organization_id", "cases", ["organization_id"])

    op.create_table(
        "tasks",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", name="fk_tasks_organization_id_organizations"),
            nullable=False,
        ),
        sa.Column(
            "case_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cases.id", name="fk_tasks_case_id_cases"),
            nullable=False,
        ),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("group", sa.String(100), nullable=True),
        sa.Column("description", sa.String, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="Waiting"),
        sa.Column(
            "assignee_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", name="fk_tasks_assignee_id_users"),
            nullable=True,
        ),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("order_index", sa.Integer, nullable=False, server_default="0"),
        sa.Column("mandatory", sa.Boolean(), nullable=False, server_default="false"),
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
    op.create_index("ix_tasks_organization_id", "tasks", ["organization_id"])
    op.create_index("ix_tasks_case_id", "tasks", ["case_id"])

    op.create_table(
        "task_logs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "task_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tasks.id", name="fk_task_logs_task_id_tasks"),
            nullable=False,
        ),
        sa.Column(
            "author_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", name="fk_task_logs_author_id_users"),
            nullable=True,
        ),
        sa.Column("content", sa.String, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_task_logs_task_id", "task_logs", ["task_id"])


def downgrade() -> None:
    op.drop_index("ix_task_logs_task_id", table_name="task_logs")
    op.drop_table("task_logs")
    op.drop_index("ix_tasks_case_id", table_name="tasks")
    op.drop_index("ix_tasks_organization_id", table_name="tasks")
    op.drop_table("tasks")
    op.drop_index("ix_cases_organization_id", table_name="cases")
    op.drop_table("cases")
