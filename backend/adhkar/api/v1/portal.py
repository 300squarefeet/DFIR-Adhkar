"""External-collaborator portal API.

Distinct from /v1/cases because Portal users are not org members — they
have per-case grants via CaseShare. The portal endpoint joins on
CaseShare(user_id=current_user, revoked_at IS NULL) to surface ONLY the
cases the user has been granted access to."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from adhkar.api.deps import CurrentUser, get_current_user, get_db
from adhkar.db.models import Case, CaseShare, Comment

router = APIRouter(prefix="/v1/portal", tags=["portal"])


class PortalCaseRow(BaseModel):
    id: UUID
    number: int
    title: str
    severity: int
    tlp: str
    stage: str
    status: str
    updated_at: datetime
    can_comment: bool
    can_upload: bool


class PortalCommentDTO(BaseModel):
    id: UUID
    content: str
    created_at: datetime


class PortalCommentCreate(BaseModel):
    content: str


@router.get("/cases", response_model=list[PortalCaseRow])
async def list_my_shared_cases(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[PortalCaseRow]:
    rows = (
        await db.execute(
            select(CaseShare, Case)
            .join(Case, Case.id == CaseShare.case_id)
            .where(
                CaseShare.user_id == user.user_id,
                CaseShare.revoked_at.is_(None),
                Case.deleted_at.is_(None),
            )
            .order_by(Case.updated_at.desc())
        )
    ).all()
    return [
        PortalCaseRow(
            id=c.id,
            number=c.number,
            title=c.title,
            severity=c.severity,
            tlp=c.tlp,
            stage=c.stage,
            status=c.status,
            updated_at=c.updated_at,
            can_comment=s.can_comment,
            can_upload=s.can_upload,
        )
        for s, c in rows
    ]


async def _verify_share(
    db: AsyncSession, user_id: UUID, case_id: UUID, require_comment: bool = False
) -> CaseShare:
    share = (
        await db.execute(
            select(CaseShare).where(
                CaseShare.user_id == user_id,
                CaseShare.case_id == case_id,
                CaseShare.revoked_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if share is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "case_not_shared_with_you")
    if require_comment and not share.can_comment:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "comment_not_permitted_for_share")
    return share


@router.get("/cases/{case_id}/comments", response_model=list[PortalCommentDTO])
async def list_portal_comments(
    case_id: UUID,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[PortalCommentDTO]:
    await _verify_share(db, user.user_id, case_id)
    rows = (
        (
            await db.execute(
                select(Comment).where(Comment.case_id == case_id).order_by(Comment.created_at)
            )
        )
        .scalars()
        .all()
    )
    return [PortalCommentDTO(id=c.id, content=c.content, created_at=c.created_at) for c in rows]


@router.post(
    "/cases/{case_id}/comments",
    response_model=PortalCommentDTO,
    status_code=status.HTTP_201_CREATED,
)
async def add_portal_comment(
    case_id: UUID,
    body: PortalCommentCreate,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PortalCommentDTO:
    share = await _verify_share(db, user.user_id, case_id, require_comment=True)
    case_org = (
        await db.execute(select(Case.organization_id).where(Case.id == case_id))
    ).scalar_one_or_none()
    if case_org is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "case_not_found")
    if share.organization_id != case_org:
        raise HTTPException(status.HTTP_409_CONFLICT, "share_org_mismatch")
    c = Comment(
        organization_id=case_org,
        case_id=case_id,
        author_id=user.user_id,
        content=body.content[:8000],
    )
    db.add(c)
    await db.flush()
    return PortalCommentDTO(id=c.id, content=c.content, created_at=c.created_at)
