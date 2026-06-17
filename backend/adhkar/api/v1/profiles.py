"""Profile management endpoints (RBAC editor)."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from adhkar.api.deps import CurrentUser, get_db, require_current_org, require_permission
from adhkar.auth.permissions import validate_permissions
from adhkar.db.models import Profile, UserOrgMembership

router = APIRouter(prefix="/v1/profiles", tags=["profiles"])


class ProfileDTO(BaseModel):
    id: UUID
    organization_id: UUID
    name: str
    description: str | None
    permissions: list[str]
    is_default: bool


class ProfileCreate(BaseModel):
    name: str
    description: str | None = None
    permissions: list[str]


class ProfilePatch(BaseModel):
    name: str | None = None
    description: str | None = None
    permissions: list[str] | None = None


@router.get("", response_model=list[ProfileDTO])
async def list_profiles(
    _user: Annotated[CurrentUser, Depends(require_permission("manageProfile"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
    with_permission: str | None = None,
) -> list[ProfileDTO]:
    """List profiles in the current org. Optional `with_permission=<key>`
    keeps only profiles whose permissions JSON array contains that key
    — answers "which roles can manage notifications" without paging the
    full set and filtering client-side."""
    stmt = select(Profile).where(Profile.organization_id == org_id)
    if with_permission is not None:
        stmt = stmt.where(Profile.permissions.contains([with_permission]))
    rows = (await db.execute(stmt)).scalars().all()
    return [_to_dto(p) for p in rows]


@router.post("", response_model=ProfileDTO, status_code=status.HTTP_201_CREATED)
async def create_profile(
    body: ProfileCreate,
    _user: Annotated[CurrentUser, Depends(require_permission("manageProfile"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProfileDTO:
    try:
        perms = validate_permissions(body.permissions)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    profile = Profile(
        organization_id=org_id,
        name=body.name,
        description=body.description,
        permissions=perms,
        is_default=False,
    )
    db.add(profile)
    await db.flush()
    return _to_dto(profile)


@router.get("/{profile_id}", response_model=ProfileDTO)
async def get_profile(
    profile_id: UUID,
    _user: Annotated[CurrentUser, Depends(require_permission("manageProfile"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProfileDTO:
    p = (
        await db.execute(
            select(Profile).where(Profile.id == profile_id, Profile.organization_id == org_id)
        )
    ).scalar_one_or_none()
    if not p:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "profile_not_found")
    return _to_dto(p)


@router.patch("/{profile_id}", response_model=ProfileDTO)
async def patch_profile(
    profile_id: UUID,
    body: ProfilePatch,
    _user: Annotated[CurrentUser, Depends(require_permission("manageProfile"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProfileDTO:
    p = (
        await db.execute(
            select(Profile).where(Profile.id == profile_id, Profile.organization_id == org_id)
        )
    ).scalar_one_or_none()
    if not p:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "profile_not_found")
    # Lock org-admin permission edit (always has all permissions)
    if p.is_default and p.name == "org-admin" and body.permissions is not None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "cannot_edit_org_admin_permissions")
    if body.name is not None:
        p.name = body.name
    if body.description is not None:
        p.description = body.description
    if body.permissions is not None:
        try:
            p.permissions = validate_permissions(body.permissions)
        except ValueError as e:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    await db.flush()
    return _to_dto(p)


@router.delete("/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_profile(
    profile_id: UUID,
    _user: Annotated[CurrentUser, Depends(require_permission("manageProfile"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    p = (
        await db.execute(
            select(Profile).where(Profile.id == profile_id, Profile.organization_id == org_id)
        )
    ).scalar_one_or_none()
    if not p:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "profile_not_found")
    if p.is_default:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "cannot_delete_default_profile")
    # Block delete if in-use by any membership
    in_use = (
        await db.execute(
            select(UserOrgMembership).where(UserOrgMembership.profile_id == profile_id)
        )
    ).scalar_one_or_none()
    if in_use:
        raise HTTPException(status.HTTP_409_CONFLICT, "profile_in_use")
    await db.delete(p)
    await db.flush()


def _to_dto(p: Profile) -> ProfileDTO:
    return ProfileDTO(
        id=p.id,
        organization_id=p.organization_id,
        name=p.name,
        description=p.description,
        permissions=list(p.permissions),
        is_default=p.is_default,
    )
