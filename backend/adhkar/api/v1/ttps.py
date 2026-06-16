"""TTP catalog + per-case TTP endpoints (Phase 5)."""

from __future__ import annotations

from datetime import date as date_cls
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from adhkar.api.deps import (
    CurrentUser,
    get_db,
    require_current_org,
    require_permission,
)
from adhkar.db.models import Case, CaseTtp, TtpCatalogEntry

router = APIRouter(tags=["ttps"])


class CatalogEntryDTO(BaseModel):
    id: UUID
    technique_id: str
    name: str
    tactic: str
    description: str | None
    url: str | None
    is_subtechnique: bool


class CatalogEntryUpsert(BaseModel):
    technique_id: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=300)
    tactic: str = Field(min_length=1, max_length=80)
    description: str | None = None
    url: str | None = Field(default=None, max_length=500)
    is_subtechnique: bool = False


class CaseTtpDTO(BaseModel):
    id: UUID
    case_id: UUID
    technique_id: str
    tactic: str
    occurrence_date: date_cls | None
    procedure_note: str | None
    created_by: UUID | None
    created_at: datetime


class CaseTtpCreate(BaseModel):
    technique_id: str = Field(min_length=1, max_length=20)
    occurrence_date: date_cls | None = None
    procedure_note: str | None = None


def _catalog_dto(t: TtpCatalogEntry) -> CatalogEntryDTO:
    return CatalogEntryDTO(
        id=t.id,
        technique_id=t.technique_id,
        name=t.name,
        tactic=t.tactic,
        description=t.description,
        url=t.url,
        is_subtechnique=t.is_subtechnique,
    )


def _case_ttp_dto(t: CaseTtp) -> CaseTtpDTO:
    return CaseTtpDTO(
        id=t.id,
        case_id=t.case_id,
        technique_id=t.technique_id,
        tactic=t.tactic,
        occurrence_date=t.occurrence_date,
        procedure_note=t.procedure_note,
        created_by=t.created_by,
        created_at=t.created_at,
    )


# ---------- Catalog (global, admin-managed) ----------


@router.get("/v1/ttps/catalog", response_model=list[CatalogEntryDTO])
async def list_catalog(
    _user: Annotated[CurrentUser, Depends(require_permission("viewCase"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    tactic: str | None = None,
    query: str | None = None,
    limit: int = 100,
) -> list[CatalogEntryDTO]:
    stmt = select(TtpCatalogEntry)
    if tactic:
        stmt = stmt.where(TtpCatalogEntry.tactic == tactic)
    if query:
        like = f"%{query}%"
        stmt = stmt.where(
            (TtpCatalogEntry.technique_id.ilike(like)) | (TtpCatalogEntry.name.ilike(like))
        )
    stmt = stmt.order_by(TtpCatalogEntry.technique_id).limit(limit)
    rows = (await db.execute(stmt)).scalars().all()
    return [_catalog_dto(t) for t in rows]


@router.put("/v1/ttps/catalog", response_model=CatalogEntryDTO)
async def upsert_catalog_entry(
    body: CatalogEntryUpsert,
    _user: Annotated[CurrentUser, Depends(require_permission("manageConfig"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CatalogEntryDTO:
    existing = (
        await db.execute(
            select(TtpCatalogEntry).where(TtpCatalogEntry.technique_id == body.technique_id)
        )
    ).scalar_one_or_none()
    if existing:
        existing.name = body.name
        existing.tactic = body.tactic
        existing.description = body.description
        existing.url = body.url
        existing.is_subtechnique = body.is_subtechnique
        await db.flush()
        return _catalog_dto(existing)
    entry = TtpCatalogEntry(
        technique_id=body.technique_id,
        name=body.name,
        tactic=body.tactic,
        description=body.description,
        url=body.url,
        is_subtechnique=body.is_subtechnique,
    )
    db.add(entry)
    await db.flush()
    return _catalog_dto(entry)


# ---------- Case TTP refs ----------


async def _load_case(db: AsyncSession, org_id: UUID, case_id: UUID) -> Case:
    c = (
        await db.execute(
            select(Case).where(
                Case.id == case_id, Case.organization_id == org_id, Case.deleted_at.is_(None)
            )
        )
    ).scalar_one_or_none()
    if not c:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "case_not_found")
    return c


@router.get("/v1/cases/{case_id}/ttps", response_model=list[CaseTtpDTO])
async def list_case_ttps(
    case_id: UUID,
    _user: Annotated[CurrentUser, Depends(require_permission("viewCase"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[CaseTtpDTO]:
    await _load_case(db, org_id, case_id)
    rows = (
        (
            await db.execute(
                select(CaseTtp)
                .where(CaseTtp.case_id == case_id, CaseTtp.organization_id == org_id)
                .order_by(CaseTtp.tactic, CaseTtp.technique_id)
            )
        )
        .scalars()
        .all()
    )
    return [_case_ttp_dto(t) for t in rows]


@router.post(
    "/v1/cases/{case_id}/ttps", response_model=CaseTtpDTO, status_code=status.HTTP_201_CREATED
)
async def add_case_ttp(
    case_id: UUID,
    body: CaseTtpCreate,
    user: Annotated[CurrentUser, Depends(require_permission("manageCase"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CaseTtpDTO:
    await _load_case(db, org_id, case_id)
    catalog = (
        await db.execute(
            select(TtpCatalogEntry).where(TtpCatalogEntry.technique_id == body.technique_id)
        )
    ).scalar_one_or_none()
    if not catalog:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "technique_not_in_catalog")
    ref = CaseTtp(
        organization_id=org_id,
        case_id=case_id,
        technique_id=catalog.technique_id,
        tactic=catalog.tactic,
        occurrence_date=body.occurrence_date,
        procedure_note=body.procedure_note,
        created_by=user.user_id,
    )
    db.add(ref)
    try:
        await db.flush()
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "technique_already_on_case") from e
    return _case_ttp_dto(ref)


class CaseTtpPatch(BaseModel):
    procedure_note: str | None = None
    occurrence_date: date_cls | None = None


@router.patch("/v1/case-ttps/{ttp_id}", response_model=CaseTtpDTO)
async def patch_case_ttp(
    ttp_id: UUID,
    body: CaseTtpPatch,
    _user: Annotated[CurrentUser, Depends(require_permission("manageCase"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CaseTtpDTO:
    t = (
        await db.execute(
            select(CaseTtp).where(CaseTtp.id == ttp_id, CaseTtp.organization_id == org_id)
        )
    ).scalar_one_or_none()
    if t is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "case_ttp_not_found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(t, field, value)
    await db.flush()
    return _case_ttp_dto(t)


@router.get(
    "/v1/cases-by-technique/{technique_id}",
    response_model=list[dict[str, Any]],
)
async def cases_by_technique(
    technique_id: str,
    _user: Annotated[CurrentUser, Depends(require_permission("viewCase"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[dict[str, Any]]:
    """Drill-down: every case in the org that carries the given technique.

    Returns the case stub (id, number, title, severity, stage) — the UI
    links each row to the existing case detail page."""
    rows = (
        await db.execute(
            select(Case.id, Case.number, Case.title, Case.severity, Case.stage)
            .join(CaseTtp, CaseTtp.case_id == Case.id)
            .where(
                Case.organization_id == org_id,
                Case.deleted_at.is_(None),
                CaseTtp.technique_id == technique_id,
            )
            .order_by(Case.number.desc())
            .limit(200)
        )
    ).all()
    return [
        {
            "id": str(r[0]),
            "number": int(r[1]),
            "title": str(r[2]),
            "severity": int(r[3]),
            "stage": str(r[4]),
        }
        for r in rows
    ]


@router.delete("/v1/case-ttps/{ttp_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_case_ttp(
    ttp_id: UUID,
    _user: Annotated[CurrentUser, Depends(require_permission("manageCase"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    t = (
        await db.execute(
            select(CaseTtp).where(CaseTtp.id == ttp_id, CaseTtp.organization_id == org_id)
        )
    ).scalar_one_or_none()
    if not t:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "case_ttp_not_found")
    await db.delete(t)
    await db.flush()
