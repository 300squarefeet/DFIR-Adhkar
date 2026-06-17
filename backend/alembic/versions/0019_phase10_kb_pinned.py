"""Phase 10 (RC75): kb_pages.pinned for runbook pinning.

Revision ID: 0019
Revises: 0018
Create Date: 2026-06-17
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "kb_pages",
        sa.Column("pinned", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("kb_pages", "pinned")
