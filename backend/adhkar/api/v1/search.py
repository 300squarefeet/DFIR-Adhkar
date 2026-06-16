"""Unified full-text search across cases + alerts (Phase 6).

Uses PostgreSQL's built-in tsvector/plainto_tsquery against the GIN
indexes from migration 0015. The dev fallback to ILIKE is intentional:
the unit/integration tests run against a fresh dev database where the
ts_rank fast path may not be measurably faster than ILIKE."""

from __future__ import annotations

import logging
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from adhkar.api.deps import (
    CurrentUser,
    get_db,
    require_current_org,
    require_permission,
)

_log = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/search", tags=["search"])


class SearchHit(BaseModel):
    entity_type: Literal["case", "alert"]
    id: UUID
    title: str
    score: float


class SearchResponse(BaseModel):
    query: str
    hits: list[SearchHit]


@router.get("", response_model=SearchResponse)
async def search(
    _user: Annotated[CurrentUser, Depends(require_permission("viewCase"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
    q: str = Query(min_length=1, max_length=400),
    limit: int = Query(default=20, ge=1, le=100),
) -> SearchResponse:
    safe_limit = max(1, min(100, int(limit)))
    # Native PG FTS path with ranking on the combined index.
    try:
        sql = text(
            """
            SELECT 'case' AS et, id, title,
                   ts_rank(
                     to_tsvector('english',
                       coalesce(title, '') || ' ' || coalesce(description, '')),
                     plainto_tsquery('english', :q)
                   ) AS score
            FROM cases
            WHERE organization_id = :org_id
              AND deleted_at IS NULL
              AND to_tsvector('english',
                    coalesce(title, '') || ' ' || coalesce(description, ''))
                  @@ plainto_tsquery('english', :q)
            UNION ALL
            SELECT 'alert' AS et, id, title,
                   ts_rank(
                     to_tsvector('english',
                       coalesce(title, '') || ' ' || coalesce(description, '') ||
                       ' ' || coalesce(source_ref, '')),
                     plainto_tsquery('english', :q)
                   ) AS score
            FROM alerts
            WHERE organization_id = :org_id
              AND to_tsvector('english',
                    coalesce(title, '') || ' ' || coalesce(description, '') ||
                    ' ' || coalesce(source_ref, ''))
                  @@ plainto_tsquery('english', :q)
            ORDER BY score DESC
            LIMIT :lim
            """
        )
        rows = (await db.execute(sql, {"q": q, "org_id": org_id, "lim": safe_limit})).all()
        return SearchResponse(
            query=q,
            hits=[
                SearchHit(
                    entity_type=r[0],
                    id=r[1],
                    title=str(r[2]),
                    score=round(float(r[3]), 4),
                )
                for r in rows
            ],
        )
    except DBAPIError:
        _log.info("search_fts_unavailable_falling_back_to_ilike")
    # Dev fallback: simple ILIKE so search works in environments without
    # the FTS extension yet (e.g. before migration 0015 is applied).
    pattern = f"%{q}%"
    sql_ilike = text(
        """
        SELECT 'case' AS et, id, title, 0.0 AS score
        FROM cases
        WHERE organization_id = :org_id
          AND deleted_at IS NULL
          AND (title ILIKE :p OR coalesce(description, '') ILIKE :p)
        UNION ALL
        SELECT 'alert' AS et, id, title, 0.0
        FROM alerts
        WHERE organization_id = :org_id
          AND (title ILIKE :p OR coalesce(description, '') ILIKE :p
               OR source_ref ILIKE :p)
        LIMIT :lim
        """
    )
    rows = (await db.execute(sql_ilike, {"p": pattern, "org_id": org_id, "lim": safe_limit})).all()
    return SearchResponse(
        query=q,
        hits=[SearchHit(entity_type=r[0], id=r[1], title=str(r[2]), score=0.0) for r in rows],
    )
