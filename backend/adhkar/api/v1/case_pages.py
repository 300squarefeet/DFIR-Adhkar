"""Case wiki page endpoints (Phase 3c)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
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
from adhkar.db.models import Case, CasePage

router = APIRouter(tags=["case-pages"])


class CasePageDTO(BaseModel):
    id: UUID
    case_id: UUID
    slug: str
    title: str
    content: str
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime


class CasePageCreate(BaseModel):
    slug: str = Field(min_length=1, max_length=200, pattern=r"^[a-z0-9][a-z0-9-_]*$")
    title: str = Field(min_length=1, max_length=300)
    content: str = ""


class CasePagePatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    content: str | None = None


def _to_dto(p: CasePage) -> CasePageDTO:
    return CasePageDTO(
        id=p.id,
        case_id=p.case_id,
        slug=p.slug,
        title=p.title,
        content=p.content,
        created_by=p.created_by,
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


async def _load_case_or_404(db: AsyncSession, org_id: UUID, case_id: UUID) -> Case:
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


@router.get("/v1/cases/{case_id}/pages", response_model=list[CasePageDTO])
async def list_case_pages(
    case_id: UUID,
    _user: Annotated[CurrentUser, Depends(require_permission("viewCase"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
    q: str | None = None,
    updated_since: datetime | None = None,
) -> list[CasePageDTO]:
    """Per-case wiki pages, alphabetical. Optional `q=<substring>`
    case-insensitive ilike across title and content; `updated_since=
    <ISO>` switches sort to updated_at DESC so polling cursors land
    on the latest edits."""
    await _load_case_or_404(db, org_id, case_id)
    stmt = select(CasePage).where(CasePage.case_id == case_id, CasePage.organization_id == org_id)
    if q is not None and q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where((CasePage.title.ilike(like)) | (CasePage.content.ilike(like)))
    if updated_since is not None:
        stmt = stmt.where(CasePage.updated_at >= updated_since).order_by(CasePage.updated_at.desc())
    else:
        stmt = stmt.order_by(CasePage.title)
    rows = (await db.execute(stmt)).scalars().all()
    return [_to_dto(p) for p in rows]


@router.post(
    "/v1/cases/{case_id}/pages",
    response_model=CasePageDTO,
    status_code=status.HTTP_201_CREATED,
)
async def create_case_page(
    case_id: UUID,
    body: CasePageCreate,
    user: Annotated[CurrentUser, Depends(require_permission("manageCase"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CasePageDTO:
    await _load_case_or_404(db, org_id, case_id)
    p = CasePage(
        organization_id=org_id,
        case_id=case_id,
        slug=body.slug,
        title=body.title,
        content=body.content,
        created_by=user.user_id,
    )
    db.add(p)
    try:
        await db.flush()
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "slug_already_exists_for_case") from e
    return _to_dto(p)


@router.patch("/v1/case-pages/{page_id}", response_model=CasePageDTO)
async def patch_case_page(
    page_id: UUID,
    body: CasePagePatch,
    _user: Annotated[CurrentUser, Depends(require_permission("manageCase"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CasePageDTO:
    p = (
        await db.execute(
            select(CasePage).where(CasePage.id == page_id, CasePage.organization_id == org_id)
        )
    ).scalar_one_or_none()
    if p is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "case_page_not_found")
    patch = body.model_dump(exclude_unset=True)
    for field, value in patch.items():
        setattr(p, field, value)
    await db.flush()
    return _to_dto(p)


@router.delete("/v1/case-pages/{page_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_case_page(
    page_id: UUID,
    _user: Annotated[CurrentUser, Depends(require_permission("manageCase"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    p = (
        await db.execute(
            select(CasePage).where(CasePage.id == page_id, CasePage.organization_id == org_id)
        )
    ).scalar_one_or_none()
    if p is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "case_page_not_found")
    await db.delete(p)
    await db.flush()
