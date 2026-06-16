"""Phase 8 (RAG, prod): add native pgvector column + ivfflat index on case_embeddings.

We keep `embedding_text` for backward-compat reads while introducing a real
vector(128) column populated from the text repr. The similarity endpoint
will fall back to text+cosine if the vector column is empty; once this
migration runs against existing data, a one-shot backfill script (out of
this migration's scope to keep it pure DDL) populates the column.

Revision ID: 0014
Revises: 0013
Create Date: 2026-06-17
"""

from __future__ import annotations

from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add vector(128) column. Default-null so existing rows survive without backfill.
    op.execute("ALTER TABLE case_embeddings ADD COLUMN embedding vector(128)")
    # IVFFlat index for cosine distance. lists=100 is a sensible default for
    # up to ~100k rows; tune via ALTER INDEX later as the corpus grows.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_case_embeddings_embedding_ivfflat "
        "ON case_embeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_case_embeddings_embedding_ivfflat")
    op.execute("ALTER TABLE case_embeddings DROP COLUMN IF EXISTS embedding")
