"""Organizations endpoints + org sharing minimal."""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from adhkar.api.deps import CurrentUser, get_current_user, get_db, require_permission
from adhkar.db.models import Organization, OrgSharing, UserOrgMembership

router = APIRouter(prefix="/v1/organizations", tags=["organizations"])


class OrgDTO(BaseModel):
    id: UUID
    name: str
    slug: str
    description: str | None
    require_mfa: bool
    locked: bool


class OrgPatch(BaseModel):
    name: str | None = None
    description: str | None = None
    require_mfa: bool | None = None
    locked: bool | None = None


class SharingDTO(BaseModel):
    id: UUID
    source_org_id: UUID
    target_org_id: UUID
    kind: Literal["peer", "parent"]


class SharingCreate(BaseModel):
    target_org_id: UUID
    kind: Literal["peer", "parent"]


@router.get("", response_model=list[OrgDTO])
async def list_my_orgs(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[OrgDTO]:
    """List orgs the current user is a member of."""
    stmt = (
        select(Organization)
        .join(UserOrgMembership, UserOrgMembership.organization_id == Organization.id)
        .where(UserOrgMembership.user_id == user.user_id, Organization.deleted_at.is_(None))
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [_to_dto(o) for o in rows]


@router.get("/{org_id}", response_model=OrgDTO)
async def get_org(
    org_id: UUID,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OrgDTO:
    membership = (
        await db.execute(
            select(UserOrgMembership).where(
                UserOrgMembership.user_id == user.user_id,
                UserOrgMembership.organization_id == org_id,
            )
        )
    ).scalar_one_or_none()
    if not membership:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "org_not_found")
    org = (await db.execute(select(Organization).where(Organization.id == org_id))).scalar_one()
    return _to_dto(org)


@router.patch("/{org_id}", response_model=OrgDTO)
async def patch_org(
    org_id: UUID,
    body: OrgPatch,
    _user: Annotated[CurrentUser, Depends(require_permission("manageOrganization"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OrgDTO:
    org = (
        await db.execute(select(Organization).where(Organization.id == org_id))
    ).scalar_one_or_none()
    if not org:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "org_not_found")
    if body.name is not None:
        org.name = body.name
    if body.description is not None:
        org.description = body.description
    if body.require_mfa is not None:
        org.require_mfa = body.require_mfa
    if body.locked is not None:
        org.locked = body.locked
    await db.flush()
    return _to_dto(org)


# --- Org sharing ---


@router.get("/{org_id}/sharing", response_model=list[SharingDTO])
async def list_sharings(
    org_id: UUID,
    _user: Annotated[CurrentUser, Depends(require_permission("manageOrganization"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[SharingDTO]:
    rows = (
        (await db.execute(select(OrgSharing).where(OrgSharing.source_org_id == org_id)))
        .scalars()
        .all()
    )
    return [
        SharingDTO(
            id=r.id,
            source_org_id=r.source_org_id,
            target_org_id=r.target_org_id,
            kind=r.kind,  # type: ignore[arg-type]
        )
        for r in rows
    ]


@router.post("/{org_id}/sharing", response_model=SharingDTO, status_code=status.HTTP_201_CREATED)
async def create_sharing(
    org_id: UUID,
    body: SharingCreate,
    user: Annotated[CurrentUser, Depends(require_permission("manageOrganization"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SharingDTO:
    if body.target_org_id == org_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "cannot_link_to_self")
    target = (
        await db.execute(select(Organization).where(Organization.id == body.target_org_id))
    ).scalar_one_or_none()
    if not target:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "target_org_not_found")
    row = OrgSharing(
        source_org_id=org_id,
        target_org_id=body.target_org_id,
        kind=body.kind,
        created_by=user.user_id,
    )
    db.add(row)
    await db.flush()
    return SharingDTO(
        id=row.id,
        source_org_id=row.source_org_id,
        target_org_id=row.target_org_id,
        kind=row.kind,  # type: ignore[arg-type]
    )


@router.delete("/{org_id}/sharing/{sharing_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sharing(
    org_id: UUID,
    sharing_id: UUID,
    _user: Annotated[CurrentUser, Depends(require_permission("manageOrganization"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    row = (
        await db.execute(
            select(OrgSharing).where(
                OrgSharing.id == sharing_id, OrgSharing.source_org_id == org_id
            )
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "sharing_not_found")
    await db.delete(row)
    await db.flush()


def _to_dto(o: Organization) -> OrgDTO:
    return OrgDTO(
        id=o.id,
        name=o.name,
        slug=o.slug,
        description=o.description,
        require_mfa=o.require_mfa,
        locked=o.locked,
    )
