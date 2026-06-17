"""Observable CRUD endpoints (Phase 2)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
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


@router.get("/search", response_model=list[ObservableDTO])
async def search_observables(
    _user: Annotated[CurrentUser, Depends(require_permission("viewObservable"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
    q: str = "",
    data_type: str | None = None,
    only_unattached: bool = False,
    limit: int = 20,
) -> list[ObservableDTO]:
    """Substring search across (data_type, data, tags). Used by the
    CaseDetailPage observable-attach picker; orders by created_at desc
    so the most recent matches surface first."""
    safe_limit = max(1, min(100, int(limit)))
    pattern = f"%{q.strip()}%" if q.strip() else "%"
    stmt = select(Observable).where(
        Observable.organization_id == org_id, Observable.deleted_at.is_(None)
    )
    if data_type:
        stmt = stmt.where(Observable.data_type == data_type)
    if only_unattached:
        stmt = stmt.where(Observable.case_id.is_(None))
    if q.strip():
        stmt = stmt.where(Observable.data.ilike(pattern))
    stmt = stmt.order_by(Observable.created_at.desc()).limit(safe_limit)
    rows = (await db.execute(stmt)).scalars().all()
    return [_to_dto(o) for o in rows]


@router.get("/recent", response_model=list[ObservableDTO])
async def list_recent_observables(
    _user: Annotated[CurrentUser, Depends(require_permission("viewObservable"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 10,
    is_ioc: bool | None = None,
    data_type: str | None = None,
) -> list[ObservableDTO]:
    """N most-recently-updated non-deleted observables (`updated_at`
    DESC), default 10, cap 50. Optional `is_ioc=true` keeps only
    flagged IOCs. Optional `data_type=<name>` exact-match filter (e.g.
    `ip`, `hash`, `domain`). Mirrors /v1/cases/recent + /v1/alerts/recent
    + /v1/tasks/recent for dashboard symmetry."""
    safe_limit = max(1, min(50, int(limit)))
    stmt = (
        select(Observable)
        .where(Observable.organization_id == org_id, Observable.deleted_at.is_(None))
        .order_by(Observable.updated_at.desc())
        .limit(safe_limit)
    )
    if is_ioc is True:
        stmt = stmt.where(Observable.is_ioc.is_(True))
    elif is_ioc is False:
        stmt = stmt.where(Observable.is_ioc.is_(False))
    if data_type is not None:
        stmt = stmt.where(Observable.data_type == data_type)
    rows = (await db.execute(stmt)).scalars().all()
    return [_to_dto(o) for o in rows]


@router.get("", response_model=list[ObservableDTO])
async def list_observables(
    _user: Annotated[CurrentUser, Depends(require_permission("viewObservable"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
    data_type: str | None = None,
    is_ioc: bool | None = None,
    sighted: bool | None = None,
    tlp: Literal["white", "green", "amber", "amber-strict", "red"] | None = None,
    tag: str | None = None,
    limit: int = 100,
) -> list[ObservableDTO]:
    stmt = select(Observable).where(
        Observable.organization_id == org_id, Observable.deleted_at.is_(None)
    )
    if data_type:
        stmt = stmt.where(Observable.data_type == data_type)
    if is_ioc is not None:
        stmt = stmt.where(Observable.is_ioc == is_ioc)
    if sighted is not None:
        stmt = stmt.where(Observable.sighted == sighted)
    if tlp:
        stmt = stmt.where(Observable.tlp == tlp)
    if tag:
        # JSONB array contains — works on text[] columns via overlap when not JSONB.
        stmt = stmt.where(Observable.tags.contains([tag]))
    stmt = stmt.order_by(Observable.created_at.desc()).limit(limit)
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


class CaseRef(BaseModel):
    case_id: UUID
    number: int
    title: str
    severity: int
    stage: str


@router.get("/{observable_id}/case-refs", response_model=list[CaseRef])
async def observable_case_refs(
    observable_id: UUID,
    _user: Annotated[CurrentUser, Depends(require_permission("viewObservable"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 50,
) -> list[CaseRef]:
    """Cases that contain an observable with the same (data_type, data) as
    this one. Joins through Observable.case_id ignoring soft-deleted cases
    and the source observable itself. Useful for cross-case pivot when an
    IOC reappears."""
    from adhkar.db.models import Case as _Case

    safe_limit = max(1, min(200, int(limit)))
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
    rows = (
        (
            await db.execute(
                select(_Case)
                .join(Observable, Observable.case_id == _Case.id)
                .where(
                    _Case.organization_id == org_id,
                    _Case.deleted_at.is_(None),
                    Observable.data_type == src.data_type,
                    Observable.data == src.data,
                    Observable.id != observable_id,
                    Observable.deleted_at.is_(None),
                )
                .order_by(_Case.number.desc())
                .limit(safe_limit)
            )
        )
        .scalars()
        .unique()
        .all()
    )
    return [
        CaseRef(
            case_id=c.id,
            number=c.number,
            title=c.title,
            severity=c.severity,
            stage=c.stage,
        )
        for c in rows
    ]


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


class BulkObservablePatch(BaseModel):
    ids: list[UUID] = Field(min_length=1, max_length=500)
    patch: ObservablePatch


class BulkObservableResult(BaseModel):
    updated: int
    ids: list[UUID]


@router.post("/bulk-patch", response_model=BulkObservableResult)
async def bulk_patch_observables(
    body: BulkObservablePatch,
    _user: Annotated[CurrentUser, Depends(require_permission("manageObservable"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> BulkObservableResult:
    """Apply one ObservablePatch to up to 500 observables. Useful for bulk
    marking IOCs sighted or flipping the is_ioc bit across a CSV import."""
    patch = body.patch.model_dump(exclude_unset=True)
    if not patch:
        return BulkObservableResult(updated=0, ids=[])
    rows = (
        (
            await db.execute(
                select(Observable).where(
                    Observable.organization_id == org_id,
                    Observable.id.in_(body.ids),
                    Observable.deleted_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    updated_ids: list[UUID] = []
    for o in rows:
        for field, value in patch.items():
            setattr(o, field, value)
        updated_ids.append(o.id)
    await db.flush()
    return BulkObservableResult(updated=len(updated_ids), ids=updated_ids)


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
