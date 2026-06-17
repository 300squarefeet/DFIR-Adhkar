"""Per-case observables view + attach/detach helpers.

The Observable model already carries an optional case_id. The endpoints
here let analysts attach existing observables to a case (or detach them)
without having to re-create the row, which matters because the same
indicator often surfaces in multiple cases — attach preserves history
+ analyzer reports."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import Integer, func, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from adhkar.api.deps import (
    CurrentUser,
    get_db,
    require_current_org,
    require_permission,
)
from adhkar.audit import audit_and_emit
from adhkar.db.models import Case, Observable

router = APIRouter(tags=["cases"])


class ObservableRow(BaseModel):
    id: UUID
    data_type: str
    data: str
    tlp: str
    pap: str
    tags: list[str]
    is_ioc: bool
    sighted: bool
    message: str | None
    created_at: datetime


class AttachPayload(BaseModel):
    observable_ids: list[UUID] = Field(min_length=1, max_length=500)


class AttachResult(BaseModel):
    attached: int
    skipped_already_attached: int
    skipped_unknown: int


async def _load_case(db: AsyncSession, org_id: UUID, case_id: UUID) -> Case:
    c = (
        await db.execute(
            select(Case).where(
                Case.id == case_id,
                Case.organization_id == org_id,
                Case.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if c is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "case_not_found")
    return c


@router.get("/v1/cases/{case_id}/observables", response_model=list[ObservableRow])
async def list_case_observables(
    case_id: UUID,
    _user: Annotated[CurrentUser, Depends(require_permission("viewCase"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
    ioc_only: bool | None = None,
    data_type: str | None = None,
) -> list[ObservableRow]:
    """Per-case observables list. `ioc_only=true` keeps only flagged
    IOCs; `data_type=<name>` exact-match scopes to one indicator type.
    Both compose with each other."""
    await _load_case(db, org_id, case_id)
    stmt = (
        select(Observable)
        .where(
            Observable.organization_id == org_id,
            Observable.case_id == case_id,
            Observable.deleted_at.is_(None),
        )
        .order_by(Observable.created_at.desc())
    )
    if ioc_only is True:
        stmt = stmt.where(Observable.is_ioc.is_(True))
    if data_type is not None:
        stmt = stmt.where(Observable.data_type == data_type)
    rows = (await db.execute(stmt)).scalars().all()
    return [
        ObservableRow(
            id=o.id,
            data_type=o.data_type,
            data=o.data,
            tlp=o.tlp,
            pap=o.pap,
            tags=list(o.tags),
            is_ioc=o.is_ioc,
            sighted=o.sighted,
            message=o.message,
            created_at=o.created_at,
        )
        for o in rows
    ]


class SimilarityCount(BaseModel):
    observable_id: UUID
    total_seen: int
    """Includes this observable. >1 means the indicator surfaced before."""


class SimilarityCountsResponse(BaseModel):
    counts: list[SimilarityCount]


class ObservablePapBucket(BaseModel):
    pap: str
    count: int


class ObservablePapSummaryResponse(BaseModel):
    case_id: UUID
    total: int
    by_pap: list[ObservablePapBucket]


@router.get(
    "/v1/cases/{case_id}/observables/pap-summary",
    response_model=ObservablePapSummaryResponse,
)
async def case_observable_pap_summary(
    case_id: UUID,
    _user: Annotated[CurrentUser, Depends(require_permission("viewObservable"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ObservablePapSummaryResponse:
    """Per-PAP count of observables attached to this case, zero-filled
    across the four canonical buckets so a sharing-posture badge can
    render without special-casing empty PAPs."""
    case = (
        await db.execute(
            select(Case).where(
                Case.id == case_id,
                Case.organization_id == org_id,
                Case.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if case is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "case_not_found")
    rows = (
        await db.execute(
            select(Observable.pap, func.count().label("n"))
            .where(
                Observable.case_id == case_id,
                Observable.organization_id == org_id,
                Observable.deleted_at.is_(None),
            )
            .group_by(Observable.pap)
        )
    ).all()
    by_pap: dict[str, int] = {str(r[0]): int(r[1]) for r in rows}
    canonical = ("white", "green", "amber", "red")
    buckets = [ObservablePapBucket(pap=p, count=by_pap.get(p, 0)) for p in canonical]
    return ObservablePapSummaryResponse(
        case_id=case_id,
        total=sum(b.count for b in buckets),
        by_pap=buckets,
    )


class ObservableTlpBucket(BaseModel):
    tlp: str
    count: int


class ObservableTlpSummaryResponse(BaseModel):
    case_id: UUID
    total: int
    by_tlp: list[ObservableTlpBucket]


@router.get(
    "/v1/cases/{case_id}/observables/tlp-summary",
    response_model=ObservableTlpSummaryResponse,
)
async def case_observable_tlp_summary(
    case_id: UUID,
    _user: Annotated[CurrentUser, Depends(require_permission("viewObservable"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ObservableTlpSummaryResponse:
    """Per-TLP count of observables attached to this case, zero-filled
    across the five canonical buckets so a sensitivity-posture badge
    can render without empty-bucket quirks. Companion to the RC196
    PAP summary."""
    case = (
        await db.execute(
            select(Case).where(
                Case.id == case_id,
                Case.organization_id == org_id,
                Case.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if case is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "case_not_found")
    rows = (
        await db.execute(
            select(Observable.tlp, func.count().label("n"))
            .where(
                Observable.case_id == case_id,
                Observable.organization_id == org_id,
                Observable.deleted_at.is_(None),
            )
            .group_by(Observable.tlp)
        )
    ).all()
    by_tlp: dict[str, int] = {str(r[0]): int(r[1]) for r in rows}
    canonical = ("white", "green", "amber", "amber-strict", "red")
    buckets = [ObservableTlpBucket(tlp=t, count=by_tlp.get(t, 0)) for t in canonical]
    return ObservableTlpSummaryResponse(
        case_id=case_id,
        total=sum(b.count for b in buckets),
        by_tlp=buckets,
    )


class ObservableTagsResponse(BaseModel):
    case_id: UUID
    tags: list[str]


@router.get(
    "/v1/cases/{case_id}/observables/tags",
    response_model=ObservableTagsResponse,
)
async def case_observable_tags(
    case_id: UUID,
    _user: Annotated[CurrentUser, Depends(require_permission("viewCase"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ObservableTagsResponse:
    """Union of all tags across observables attached to this case,
    sorted alphabetically. Cheap server-side aggregate so the case
    detail page can render "tags from evidence" without paging the
    full observable list."""
    await _load_case(db, org_id, case_id)
    rows = (
        await db.execute(
            select(Observable.tags).where(
                Observable.organization_id == org_id,
                Observable.case_id == case_id,
                Observable.deleted_at.is_(None),
            )
        )
    ).all()
    seen: set[str] = set()
    for (tags,) in rows:
        if tags:
            seen.update(str(t) for t in tags)
    return ObservableTagsResponse(case_id=case_id, tags=sorted(seen))


class ObservableSummaryBucket(BaseModel):
    data_type: str
    count: int
    ioc_count: int


class ObservableSummaryResponse(BaseModel):
    case_id: UUID
    total: int
    ioc_total: int
    by_type: list[ObservableSummaryBucket]


@router.get(
    "/v1/cases/{case_id}/observables/summary",
    response_model=ObservableSummaryResponse,
)
async def case_observable_summary(
    case_id: UUID,
    _user: Annotated[CurrentUser, Depends(require_permission("viewObservable"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
    since: datetime | None = None,
) -> ObservableSummaryResponse:
    """Per-data_type count of observables attached to this case, with
    IOC subtotals per bucket. 404 when the case isn't in caller's org.
    Optional `since=<ISO>` scopes the summary to observables created
    after the cursor — useful for an "evidence added this week" view."""
    case = (
        await db.execute(
            select(Case).where(
                Case.id == case_id,
                Case.organization_id == org_id,
                Case.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if case is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "case_not_found")
    summary_stmt = (
        select(
            Observable.data_type,
            func.count().label("total"),
            func.sum(func.cast(Observable.is_ioc, type_=Integer)).label("ioc_n"),
        )
        .where(
            Observable.case_id == case_id,
            Observable.organization_id == org_id,
            Observable.deleted_at.is_(None),
        )
        .group_by(Observable.data_type)
        .order_by(func.count().desc(), Observable.data_type)
    )
    if since is not None:
        summary_stmt = summary_stmt.where(Observable.created_at >= since)
    rows = (await db.execute(summary_stmt)).all()
    buckets = [
        ObservableSummaryBucket(
            data_type=str(r[0]),
            count=int(r[1]),
            ioc_count=int(r[2] or 0),
        )
        for r in rows
    ]
    return ObservableSummaryResponse(
        case_id=case_id,
        total=sum(b.count for b in buckets),
        ioc_total=sum(b.ioc_count for b in buckets),
        by_type=buckets,
    )


@router.get(
    "/v1/cases/{case_id}/observables/similarity-counts",
    response_model=SimilarityCountsResponse,
)
async def case_observable_similarity_counts(
    case_id: UUID,
    _user: Annotated[CurrentUser, Depends(require_permission("viewCase"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SimilarityCountsResponse:
    """Per-attached-observable count of org-wide sightings of the same
    (data_type, data) pair. Drives the 'seen Nx' badge on the case
    detail page so analysts spot recurrent indicators immediately."""
    await _load_case(db, org_id, case_id)
    attached = (
        await db.execute(
            select(Observable.id, Observable.data_type, Observable.data).where(
                Observable.organization_id == org_id,
                Observable.case_id == case_id,
                Observable.deleted_at.is_(None),
            )
        )
    ).all()
    if not attached:
        return SimilarityCountsResponse(counts=[])
    pairs = [(row[1], row[2]) for row in attached]
    pair_counts: dict[tuple[str, str], int] = dict.fromkeys(pairs, 0)
    rows = (
        await db.execute(
            select(
                Observable.data_type,
                Observable.data,
                func.count().label("n"),
            )
            .where(
                Observable.organization_id == org_id,
                Observable.deleted_at.is_(None),
                tuple_(Observable.data_type, Observable.data).in_(
                    [tuple_(p[0], p[1]) for p in set(pairs)]
                ),
            )
            .group_by(Observable.data_type, Observable.data)
        )
    ).all()
    for r in rows:
        pair_counts[(r[0], r[1])] = int(r[2])
    return SimilarityCountsResponse(
        counts=[
            SimilarityCount(observable_id=oid, total_seen=pair_counts.get((dt, d), 1))
            for (oid, dt, d) in attached
        ]
    )


@router.post(
    "/v1/cases/{case_id}/observables/attach",
    response_model=AttachResult,
)
async def attach_observables_to_case(
    case_id: UUID,
    body: AttachPayload,
    user: Annotated[CurrentUser, Depends(require_permission("manageCase"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AttachResult:
    """Attach existing observables (by id) to this case.

    - Rows already attached to THIS case → skipped_already_attached
    - Rows not visible in this org → skipped_unknown (silent)
    - Rows attached elsewhere are re-pointed to this case (the same
      indicator surfacing in a new case is a feature, not a conflict)
    """
    await _load_case(db, org_id, case_id)
    rows = (
        (
            await db.execute(
                select(Observable).where(
                    Observable.organization_id == org_id,
                    Observable.id.in_(body.observable_ids),
                    Observable.deleted_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    found_ids = {o.id for o in rows}
    unknown = len(set(body.observable_ids) - found_ids)
    attached = 0
    already = 0
    moved_ids: list[UUID] = []
    for o in rows:
        if o.case_id == case_id:
            already += 1
            continue
        o.case_id = case_id
        moved_ids.append(o.id)
        attached += 1
    await db.flush()
    if attached:
        await audit_and_emit(
            db,
            actor_user_id=user.user_id,
            organization_id=org_id,
            action="observables_attached",
            entity_type="case",
            entity_id=case_id,
            diff={"count": attached, "ids": [str(i) for i in moved_ids[:50]]},
        )
    return AttachResult(
        attached=attached, skipped_already_attached=already, skipped_unknown=unknown
    )


@router.post(
    "/v1/cases/{case_id}/observables/{observable_id}/detach",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def detach_observable_from_case(
    case_id: UUID,
    observable_id: UUID,
    user: Annotated[CurrentUser, Depends(require_permission("manageCase"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await _load_case(db, org_id, case_id)
    o = (
        await db.execute(
            select(Observable).where(
                Observable.id == observable_id,
                Observable.organization_id == org_id,
                Observable.case_id == case_id,
                Observable.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if o is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "observable_not_attached_to_case")
    o.case_id = None
    await db.flush()
    await audit_and_emit(
        db,
        actor_user_id=user.user_id,
        organization_id=org_id,
        action="observable_detached",
        entity_type="case",
        entity_id=case_id,
        diff={"observable_id": str(observable_id)},
    )
