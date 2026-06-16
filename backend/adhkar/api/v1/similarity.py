"""Case similarity search via embeddings.

Computes the query embedding with the default provider, then ranks
already-indexed cases in the caller's org by cosine similarity in Python.
This is the portable fallback; production swaps to a pgvector ANN query
(`ORDER BY embedding <=> $1::vector LIMIT N`) when the index is built."""

from __future__ import annotations

import json
import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from adhkar.ai.embeddings import cosine, get_embedding_router, to_pgvector_text
from adhkar.api.deps import (
    CurrentUser,
    get_db,
    require_current_org,
    require_permission,
)
from adhkar.db.models import Case, CaseEmbedding

_log = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/similarity", tags=["similarity"])


class SimilarityQuery(BaseModel):
    text: str = Field(min_length=1, max_length=8000)
    limit: int = Field(default=10, ge=1, le=50)


class SimilarityHit(BaseModel):
    case_id: UUID
    case_number: int
    title: str
    score: float


class SimilarityResponse(BaseModel):
    model: str
    hits: list[SimilarityHit]


def _parse_pgvector_text(s: str) -> list[float]:
    """Tolerate both 'pgvector' text ('[1,2,3]') and JSON ('[1,2,3]')."""
    try:
        return list(json.loads(s))
    except (ValueError, TypeError):
        # Strip brackets and split on commas as a fallback.
        inner = s.strip().lstrip("[").rstrip("]")
        return [float(p) for p in inner.split(",") if p.strip()]


@router.post("/cases", response_model=SimilarityResponse)
async def search_similar_cases(
    body: SimilarityQuery,
    _user: Annotated[CurrentUser, Depends(require_permission("viewCase"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SimilarityResponse:
    er = get_embedding_router()
    qres = await er.embed(body.text)
    # Production fast path: native pgvector ANN. Falls back to Python cosine
    # if the column doesn't exist yet (migration 0014 not applied) or all
    # rows are still text-only.
    try:
        ann_sql = text(
            """
            SELECT ce.case_id,
                   c.number,
                   c.title,
                   1 - (ce.embedding <=> CAST(:qvec AS vector)) AS score
            FROM case_embeddings ce
            JOIN cases c ON c.id = ce.case_id
            WHERE ce.organization_id = :org_id
              AND ce.model_name = :model
              AND c.deleted_at IS NULL
              AND ce.embedding IS NOT NULL
            ORDER BY ce.embedding <=> CAST(:qvec AS vector)
            LIMIT :lim
            """
        )
        ann_rows = (
            await db.execute(
                ann_sql,
                {
                    "qvec": to_pgvector_text(qres.vector),
                    "org_id": org_id,
                    "model": qres.model,
                    "lim": body.limit,
                },
            )
        ).all()
        if ann_rows:
            return SimilarityResponse(
                model=qres.model,
                hits=[
                    SimilarityHit(
                        case_id=r[0],
                        case_number=int(r[1]),
                        title=str(r[2]),
                        score=round(float(r[3]), 4),
                    )
                    for r in ann_rows
                ],
            )
    except DBAPIError:
        _log.info("similarity_ann_unavailable_falling_back_to_python_cosine")
    rows = (
        await db.execute(
            select(CaseEmbedding, Case)
            .join(Case, Case.id == CaseEmbedding.case_id)
            .where(
                CaseEmbedding.organization_id == org_id,
                CaseEmbedding.model_name == qres.model,
                Case.deleted_at.is_(None),
            )
            .limit(500)
        )
    ).all()
    scored: list[tuple[float, Case]] = []
    for emb, case in rows:
        try:
            vec = _parse_pgvector_text(emb.embedding_text)
        except ValueError:
            continue
        if len(vec) != qres.dimension:
            continue
        scored.append((cosine(qres.vector, vec), case))
    scored.sort(key=lambda x: x[0], reverse=True)
    hits = [
        SimilarityHit(case_id=c.id, case_number=c.number, title=c.title, score=round(score, 4))
        for score, c in scored[: body.limit]
    ]
    return SimilarityResponse(model=qres.model, hits=hits)
