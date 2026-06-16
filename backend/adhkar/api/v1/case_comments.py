"""Case comments + case links endpoints (Phase 3b)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from adhkar.api.deps import (
    CurrentUser,
    get_db,
    require_current_org,
    require_permission,
)
from adhkar.db.models import Case, CaseLink, Comment

router = APIRouter(tags=["cases"])

RELATION = Literal["related", "duplicate", "child_of", "caused_by", "references"]


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


# ---------- Comments ----------


class CommentDTO(BaseModel):
    id: UUID
    case_id: UUID
    author_id: UUID | None
    content: str
    created_at: datetime
    updated_at: datetime


class CommentCreate(BaseModel):
    content: str = Field(min_length=1)


class CommentPatch(BaseModel):
    content: str = Field(min_length=1)


def _comment_dto(c: Comment) -> CommentDTO:
    return CommentDTO(
        id=c.id,
        case_id=c.case_id,
        author_id=c.author_id,
        content=c.content,
        created_at=c.created_at,
        updated_at=c.updated_at,
    )


@router.get("/v1/cases/{case_id}/comments", response_model=list[CommentDTO])
async def list_comments(
    case_id: UUID,
    _user: Annotated[CurrentUser, Depends(require_permission("viewCase"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[CommentDTO]:
    await _load_case(db, org_id, case_id)
    rows = (
        (
            await db.execute(
                select(Comment)
                .where(Comment.case_id == case_id, Comment.organization_id == org_id)
                .order_by(Comment.created_at)
            )
        )
        .scalars()
        .all()
    )
    return [_comment_dto(c) for c in rows]


@router.post(
    "/v1/cases/{case_id}/comments",
    response_model=CommentDTO,
    status_code=status.HTTP_201_CREATED,
)
async def create_comment(
    case_id: UUID,
    body: CommentCreate,
    user: Annotated[CurrentUser, Depends(require_permission("manageCase"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CommentDTO:
    await _load_case(db, org_id, case_id)
    c = Comment(
        organization_id=org_id,
        case_id=case_id,
        author_id=user.user_id,
        content=body.content,
    )
    db.add(c)
    await db.flush()
    return _comment_dto(c)


@router.patch("/v1/comments/{comment_id}", response_model=CommentDTO)
async def patch_comment(
    comment_id: UUID,
    body: CommentPatch,
    user: Annotated[CurrentUser, Depends(require_permission("manageCase"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CommentDTO:
    c = (
        await db.execute(
            select(Comment).where(Comment.id == comment_id, Comment.organization_id == org_id)
        )
    ).scalar_one_or_none()
    if not c:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "comment_not_found")
    if c.author_id != user.user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not_comment_author")
    c.content = body.content
    await db.flush()
    return _comment_dto(c)


@router.delete("/v1/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_comment(
    comment_id: UUID,
    user: Annotated[CurrentUser, Depends(require_permission("manageCase"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    c = (
        await db.execute(
            select(Comment).where(Comment.id == comment_id, Comment.organization_id == org_id)
        )
    ).scalar_one_or_none()
    if not c:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "comment_not_found")
    if c.author_id != user.user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not_comment_author")
    await db.delete(c)
    await db.flush()


# ---------- Case links ----------


class CaseLinkDTO(BaseModel):
    id: UUID
    source_case_id: UUID
    target_case_id: UUID
    relation: str
    note: str | None
    created_by: UUID | None
    created_at: datetime


class CaseLinkCreate(BaseModel):
    target_case_id: UUID
    relation: RELATION = "related"
    note: str | None = Field(default=None, max_length=1000)


def _link_dto(link: CaseLink) -> CaseLinkDTO:
    return CaseLinkDTO(
        id=link.id,
        source_case_id=link.source_case_id,
        target_case_id=link.target_case_id,
        relation=link.relation,
        note=link.note,
        created_by=link.created_by,
        created_at=link.created_at,
    )


@router.get("/v1/cases/{case_id}/links", response_model=list[CaseLinkDTO])
async def list_links(
    case_id: UUID,
    _user: Annotated[CurrentUser, Depends(require_permission("viewCase"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[CaseLinkDTO]:
    await _load_case(db, org_id, case_id)
    rows = (
        (
            await db.execute(
                select(CaseLink).where(
                    CaseLink.organization_id == org_id,
                    or_(CaseLink.source_case_id == case_id, CaseLink.target_case_id == case_id),
                )
            )
        )
        .scalars()
        .all()
    )
    return [_link_dto(link) for link in rows]


@router.post(
    "/v1/cases/{case_id}/links",
    response_model=CaseLinkDTO,
    status_code=status.HTTP_201_CREATED,
)
async def create_link(
    case_id: UUID,
    body: CaseLinkCreate,
    user: Annotated[CurrentUser, Depends(require_permission("manageCase"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CaseLinkDTO:
    if case_id == body.target_case_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "cannot_link_case_to_itself")
    await _load_case(db, org_id, case_id)
    await _load_case(db, org_id, body.target_case_id)
    link = CaseLink(
        organization_id=org_id,
        source_case_id=case_id,
        target_case_id=body.target_case_id,
        relation=body.relation,
        note=body.note,
        created_by=user.user_id,
    )
    db.add(link)
    try:
        await db.flush()
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "link_already_exists") from e
    return _link_dto(link)


@router.delete("/v1/case-links/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_link(
    link_id: UUID,
    _user: Annotated[CurrentUser, Depends(require_permission("manageCase"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    link = (
        await db.execute(
            select(CaseLink).where(CaseLink.id == link_id, CaseLink.organization_id == org_id)
        )
    ).scalar_one_or_none()
    if not link:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "link_not_found")
    await db.delete(link)
    await db.flush()
