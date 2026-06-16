"""Phase 6 (search): PostgreSQL FTS GIN indexes on cases + alerts.

Per the project ADR, OpenSearch was deferred — PostgreSQL FTS handles
the volumes we expect. tsvector indexes on (title, description) for
cases and (title, description, source_ref) for alerts give us
sub-100ms search on millions of rows without an extra service.

Revision ID: 0015
Revises: 0014
Create Date: 2026-06-17
"""

from __future__ import annotations

from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_cases_fts "
        "ON cases USING GIN ("
        "to_tsvector('english', "
        "coalesce(title, '') || ' ' || coalesce(description, '')))"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_alerts_fts "
        "ON alerts USING GIN ("
        "to_tsvector('english', "
        "coalesce(title, '') || ' ' || coalesce(description, '') || ' ' || "
        "coalesce(source_ref, '')))"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_alerts_fts")
    op.execute("DROP INDEX IF EXISTS ix_cases_fts")
