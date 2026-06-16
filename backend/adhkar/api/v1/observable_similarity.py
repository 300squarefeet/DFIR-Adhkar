"""Observable similarity endpoint: 'seen before' detection.

For a given observable, returns every other observable in the same org
that shares the (data_type, data) pair — useful to surface 'this IP has
shown up in 8 previous cases this quarter' before an analyst chases a
false positive.

We deliberately match exact (data_type, data) for the first cut. Fuzzy
match (CIDR, IP/24, domain suffix) can layer on later via separate
helpers — keeps the SQL trivial and the org-boundary obvious."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from adhkar.api.deps import (
    CurrentUser,
    get_db,
    require_current_org,
    require_permission,
)
from adhkar.db.models import Case, Observable

router = APIRouter(tags=["observables"])


class SimilarObservable(BaseModel):
    id: UUID
    data_type: str
    data: str
    is_ioc: bool
    sighted: bool
    tags: list[str]
    case_id: UUID | None
    case_number: int | None
    created_at: datetime


class SimilarityResponse(BaseModel):
    source_id: UUID
    matches: list[SimilarObservable]


@router.get("/v1/observables/{observable_id}/similar", response_model=SimilarityResponse)
async def find_similar(
    observable_id: UUID,
    _user: Annotated[CurrentUser, Depends(require_permission("viewObservable"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SimilarityResponse:
    src = (
        await db.execute(
            select(Observable).where(
                Observable.id == observable_id,
                Observable.organization_id == org_id,
                Observable.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if src is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "observable_not_found")
    if src.ignore_similarity:
        return SimilarityResponse(source_id=observable_id, matches=[])
    rows = (
        await db.execute(
            select(Observable, Case.number)
            .outerjoin(Case, Case.id == Observable.case_id)
            .where(
                Observable.organization_id == org_id,
                Observable.data_type == src.data_type,
                Observable.data == src.data,
                Observable.id != observable_id,
                Observable.deleted_at.is_(None),
                Observable.ignore_similarity.is_(False),
            )
            .order_by(Observable.created_at.desc())
            .limit(100)
        )
    ).all()
    return SimilarityResponse(
        source_id=observable_id,
        matches=[
            SimilarObservable(
                id=o.id,
                data_type=o.data_type,
                data=o.data,
                is_ioc=o.is_ioc,
                sighted=o.sighted,
                tags=list(o.tags),
                case_id=o.case_id,
                case_number=int(num) if num is not None else None,
                created_at=o.created_at,
            )
            for o, num in rows
        ],
    )
