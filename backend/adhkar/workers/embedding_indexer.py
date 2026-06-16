"""Embedding indexer worker.

Polls closed cases that don't yet have a CaseEmbedding row and creates one
using the default embedding provider. Idempotent — runs each minute and
catches up; safe to interrupt at any point."""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from adhkar.ai.embeddings import EmbeddingRouter, get_embedding_router, to_pgvector_text
from adhkar.core.settings import Settings
from adhkar.db.models import Case, CaseEmbedding

_log = logging.getLogger(__name__)

_POLL_INTERVAL_SECONDS = 60
_BATCH = 25
_EXCERPT_LIMIT = 4000


def _case_text(c: Case) -> str:
    parts = [f"#{c.number}: {c.title}"]
    if c.description:
        parts.append(c.description)
    if c.resolution:
        parts.append(f"Resolution: {c.resolution}")
    if c.tags:
        parts.append("Tags: " + ", ".join(c.tags))
    return "\n".join(parts)[:_EXCERPT_LIMIT]


async def _index_one_batch(sm: async_sessionmaker[AsyncSession], embedder: EmbeddingRouter) -> int:
    async with sm() as db:
        # Closed, not-yet-embedded
        existing_ids_stmt = select(CaseEmbedding.case_id)
        already = set((await db.execute(existing_ids_stmt)).scalars())
        rows = (
            (
                await db.execute(
                    select(Case)
                    .where(Case.stage == "closed", Case.deleted_at.is_(None))
                    .order_by(Case.updated_at.desc())
                    .limit(_BATCH * 4)
                )
            )
            .scalars()
            .all()
        )
        todo = [c for c in rows if c.id not in already][:_BATCH]
        if not todo:
            return 0
        for case in todo:
            text = _case_text(case)
            result = await embedder.embed(text)
            db.add(
                CaseEmbedding(
                    organization_id=case.organization_id,
                    case_id=case.id,
                    model_name=result.model,
                    dimension=result.dimension,
                    embedding_text=to_pgvector_text(result.vector),
                    source_excerpt=text[:1000],
                )
            )
        await db.commit()
        return len(todo)


async def run_embedding_indexer(settings: Settings) -> None:
    engine = create_async_engine(str(settings.database_url))
    sm = async_sessionmaker(engine, expire_on_commit=False)
    router = get_embedding_router()
    _log.info("embedding_indexer started interval=%ds batch=%d", _POLL_INTERVAL_SECONDS, _BATCH)
    while True:
        try:
            n = await _index_one_batch(sm, router)
            if n:
                _log.info("embedding_indexer indexed %d cases", n)
        except Exception:
            _log.exception("embedding_indexer batch failed")
        await asyncio.sleep(_POLL_INTERVAL_SECONDS)
