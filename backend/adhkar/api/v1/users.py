"""User management endpoints (admin) + invite-accept (public)."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from adhkar.api.deps import (
    CurrentUser,
    get_db,
    get_settings,
    require_current_org,
    require_permission,
)
from adhkar.auth.invite import (
    InvitePayload,
    ResetPayload,
    sign_invite,
    sign_reset,
    verify_invite,
    verify_reset,
)
from adhkar.auth.password import hash_password, validate_password_policy
from adhkar.core.settings import Settings
from adhkar.db.models import Profile, User, UserOrgMembership
from adhkar.services.email import send_email

router = APIRouter(tags=["users"])


class UserDTO(BaseModel):
    id: UUID
    email: str
    display_name: str
    status: str


class InviteRequest(BaseModel):
    email: EmailStr
    display_name: str
    profile_id: UUID


class InvitePeekResponse(BaseModel):
    email: str
    org_name: str
    display_name: str


class AcceptInviteRequest(BaseModel):
    token: str
    password: str


class ForgotRequest(BaseModel):
    email: EmailStr


class ResetRequest(BaseModel):
    token: str
    new_password: str


@router.get("/v1/users", response_model=list[UserDTO])
async def list_users(
    _user: Annotated[CurrentUser, Depends(require_permission("manageUser"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[UserDTO]:
    """List users that are members of the current org."""
    stmt = (
        select(User)
        .join(UserOrgMembership, UserOrgMembership.user_id == User.id)
        .where(UserOrgMembership.organization_id == org_id, User.deleted_at.is_(None))
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [
        UserDTO(id=u.id, email=u.email, display_name=u.display_name, status=u.status) for u in rows
    ]


@router.post("/v1/users/invite", response_model=UserDTO, status_code=status.HTTP_201_CREATED)
async def invite_user(
    body: InviteRequest,
    user: Annotated[CurrentUser, Depends(require_permission("manageUser"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserDTO:
    """Create a pending_invite user, bind to current org with the named profile, send signed invite link via email."""
    existing = (await db.execute(select(User).where(User.email == body.email))).scalar_one_or_none()
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "user_email_exists")

    profile = (
        await db.execute(
            select(Profile).where(Profile.id == body.profile_id, Profile.organization_id == org_id)
        )
    ).scalar_one_or_none()
    if not profile:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "profile_not_in_org")

    new_user = User(email=body.email, display_name=body.display_name, status="pending_invite")
    db.add(new_user)
    await db.flush()
    db.add(UserOrgMembership(user_id=new_user.id, organization_id=org_id, profile_id=profile.id))
    await db.flush()

    token = sign_invite(
        settings.secret_key,
        InvitePayload(user_id=new_user.id, org_id=org_id, profile_id=profile.id),
    )
    invite_link = f"{settings.cors_origins[0] if settings.cors_origins else 'http://localhost:5173'}/invite/{token}"
    await send_email(
        settings,
        to=body.email,
        subject="You're invited to Adhkar IR",
        body=f"Hi {body.display_name},\n\n{user.user_id} has invited you to join Adhkar IR.\n\nAccept your invite within 24 hours: {invite_link}\n",
    )
    return UserDTO(
        id=new_user.id,
        email=new_user.email,
        display_name=new_user.display_name,
        status=new_user.status,
    )


@router.get("/v1/auth/invite/{token}", response_model=InvitePeekResponse)
async def peek_invite(
    token: str,
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> InvitePeekResponse:
    try:
        payload = verify_invite(settings.secret_key, token)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    user = (await db.execute(select(User).where(User.id == payload.user_id))).scalar_one_or_none()
    if not user or user.status != "pending_invite":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invite_consumed")
    from adhkar.db.models import Organization

    org = (
        await db.execute(select(Organization).where(Organization.id == payload.org_id))
    ).scalar_one()
    return InvitePeekResponse(email=user.email, org_name=org.name, display_name=user.display_name)


@router.post("/v1/auth/invite/accept", response_model=UserDTO)
async def accept_invite(
    body: AcceptInviteRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserDTO:
    try:
        payload = verify_invite(settings.secret_key, body.token)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    try:
        validate_password_policy(body.password)
    except Exception as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e

    user = (await db.execute(select(User).where(User.id == payload.user_id))).scalar_one_or_none()
    if not user or user.status != "pending_invite":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invite_consumed")

    user.password_hash = hash_password(body.password)
    user.status = "active"
    user.default_org_id = payload.org_id
    await db.flush()
    return UserDTO(id=user.id, email=user.email, display_name=user.display_name, status=user.status)


@router.post("/v1/auth/password/forgot", status_code=status.HTTP_204_NO_CONTENT)
async def forgot_password(
    body: ForgotRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Always returns 204 to avoid email enumeration; if user exists, email is sent."""
    user = (await db.execute(select(User).where(User.email == body.email))).scalar_one_or_none()
    if user and user.status == "active":
        token = sign_reset(settings.secret_key, ResetPayload(user_id=user.id))
        link = f"{settings.cors_origins[0] if settings.cors_origins else 'http://localhost:5173'}/password/reset/{token}"
        await send_email(
            settings,
            to=user.email,
            subject="Adhkar IR — password reset",
            body=f"To reset your password, follow this link within 1 hour:\n\n{link}\n\nIf you didn't request this, ignore this email.",
        )


@router.post("/v1/auth/password/reset", status_code=status.HTTP_204_NO_CONTENT)
async def reset_password(
    body: ResetRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    try:
        payload = verify_reset(settings.secret_key, body.token)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    try:
        validate_password_policy(body.new_password)
    except Exception as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    user = (await db.execute(select(User).where(User.id == payload.user_id))).scalar_one_or_none()
    if not user or user.status != "active":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "user_inactive")
    user.password_hash = hash_password(body.new_password)
    await db.flush()
