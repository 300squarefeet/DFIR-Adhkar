"""Observable CRUD endpoints (Phase 2)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
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
from adhkar.db.models import Observable
from adhkar.db.repositories.observables import ObservableRepository

router = APIRouter(prefix="/v1/observables", tags=["observables"])

TLP_VALUES: tuple[str, ...] = ("white", "green", "amber", "amber-strict", "red")
PAP_VALUES: tuple[str, ...] = ("white", "green", "amber", "red")


class ObservableDTO(BaseModel):
    id: UUID
    organization_id: UUID
    data_type: str
    data: str
    tlp: str
    pap: str
    tags: list[str]
    is_ioc: bool
    sighted: bool
    ignore_similarity: bool
    message: str | None
    created_at: datetime
    updated_at: datetime


class ObservableCreate(BaseModel):
    data_type: str
    data: str
    tlp: Literal["white", "green", "amber", "amber-strict", "red"] = "amber"
    pap: Literal["white", "green", "amber", "red"] = "amber"
    tags: list[str] = []
    is_ioc: bool = False
    sighted: bool = False
    ignore_similarity: bool = False
    message: str | None = None


class ObservablePatch(BaseModel):
    tlp: Literal["white", "green", "amber", "amber-strict", "red"] | None = None
    pap: Literal["white", "green", "amber", "red"] | None = None
    tags: list[str] | None = None
    is_ioc: bool | None = None
    sighted: bool | None = None
    ignore_similarity: bool | None = None
    message: str | None = None


def _to_dto(o: Observable) -> ObservableDTO:
    return ObservableDTO(
        id=o.id,
        organization_id=o.organization_id,
        data_type=o.data_type,
        data=o.data,
        tlp=o.tlp,
        pap=o.pap,
        tags=list(o.tags),
        is_ioc=o.is_ioc,
        sighted=o.sighted,
        ignore_similarity=o.ignore_similarity,
        message=o.message,
        created_at=o.created_at,
        updated_at=o.updated_at,
    )


@router.get("", response_model=list[ObservableDTO])
async def list_observables(
    _user: Annotated[CurrentUser, Depends(require_permission("viewObservable"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
    data_type: str | None = None,
    limit: int = 100,
) -> list[ObservableDTO]:
    stmt = select(Observable).where(
        Observable.organization_id == org_id, Observable.deleted_at.is_(None)
    )
    if data_type:
        stmt = stmt.where(Observable.data_type == data_type)
    stmt = stmt.limit(limit)
    rows = (await db.execute(stmt)).scalars().all()
    return [_to_dto(o) for o in rows]


@router.post("", response_model=ObservableDTO, status_code=status.HTTP_201_CREATED)
async def create_observable(
    body: ObservableCreate,
    user: Annotated[CurrentUser, Depends(require_permission("manageObservable"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ObservableDTO:
    repo = ObservableRepository(db, org_id)
    entity = Observable(
        organization_id=org_id,
        data_type=body.data_type,
        data=body.data,
        tlp=body.tlp,
        pap=body.pap,
        tags=body.tags,
        is_ioc=body.is_ioc,
        sighted=body.sighted,
        ignore_similarity=body.ignore_similarity,
        message=body.message,
        created_by=user.user_id,
    )
    await repo.add(entity)
    return _to_dto(entity)


@router.get("/{observable_id}", response_model=ObservableDTO)
async def get_observable(
    observable_id: UUID,
    _user: Annotated[CurrentUser, Depends(require_permission("viewObservable"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ObservableDTO:
    repo = ObservableRepository(db, org_id)
    o = await repo.get(observable_id)
    if not o or o.deleted_at:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "observable_not_found")
    return _to_dto(o)


@router.patch("/{observable_id}", response_model=ObservableDTO)
async def patch_observable(
    observable_id: UUID,
    body: ObservablePatch,
    _user: Annotated[CurrentUser, Depends(require_permission("manageObservable"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ObservableDTO:
    repo = ObservableRepository(db, org_id)
    o = await repo.get(observable_id)
    if not o or o.deleted_at:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "observable_not_found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(o, field, value)
    await db.flush()
    return _to_dto(o)


@router.delete("/{observable_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_observable(
    observable_id: UUID,
    _user: Annotated[CurrentUser, Depends(require_permission("manageObservable"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    repo = ObservableRepository(db, org_id)
    o = await repo.get(observable_id)
    if not o or o.deleted_at:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "observable_not_found")
    from datetime import UTC

    o.deleted_at = datetime.now(tz=UTC)
    await db.flush()
