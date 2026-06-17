"""User management endpoints (admin) + invite-accept (public)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from adhkar.api.deps import (
    CurrentUser,
    get_current_user,
    get_db,
    get_settings,
    require_current_org,
    require_permission,
)
from adhkar.audit import audit_and_emit
from adhkar.auth.invite import (
    InvitePayload,
    ResetPayload,
    sign_invite,
    sign_reset,
    verify_invite,
    verify_reset,
)
from adhkar.auth.password import hash_password, validate_password_policy, verify_password
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


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=12, max_length=200)


@router.get("/v1/users/search", response_model=list[UserDTO])
async def search_users(
    _user: Annotated[CurrentUser, Depends(require_permission("viewCase"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
    q: str = "",
    status: str | None = None,
    limit: int = 10,
) -> list[UserDTO]:
    """Find org members by email or display_name (ilike). Used by the
    case-assignee picker — viewCase is enough since we only expose the
    triple (id, email, display_name). Optional `status=<value>` scopes
    to one lifecycle (active/suspended/pending_invite) so the picker
    doesn't surface invitees who can't yet be assigned."""
    safe_limit = max(1, min(50, int(limit)))
    stmt = (
        select(User)
        .join(UserOrgMembership, UserOrgMembership.user_id == User.id)
        .where(
            UserOrgMembership.organization_id == org_id,
            User.deleted_at.is_(None),
        )
    )
    if q.strip():
        pattern = f"%{q.strip()}%"
        stmt = stmt.where((User.email.ilike(pattern)) | (User.display_name.ilike(pattern)))
    if status is not None:
        stmt = stmt.where(User.status == status)
    stmt = stmt.order_by(User.display_name).limit(safe_limit)
    rows = (await db.execute(stmt)).scalars().all()
    return [
        UserDTO(id=u.id, email=u.email, display_name=u.display_name, status=u.status) for u in rows
    ]


@router.get("/v1/users/recent", response_model=list[UserDTO])
async def list_recent_users(
    _user: Annotated[CurrentUser, Depends(require_permission("viewCase"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 10,
    active_within_days: int | None = None,
) -> list[UserDTO]:
    """N org members ordered by their most-recent audit-log timestamp,
    DESC. Falls back to display_name for users that have never authored
    an audit event. Default 10, cap 50. Optional `active_within_days=N`
    (1..365) restricts the audit-noise window AND drops members whose
    last_seen is older than that cutoff — useful for an "active this
    week" widget."""
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import desc, func

    from adhkar.db.models import AuditLog as _AuditLog

    safe_limit = max(1, min(50, int(limit)))
    last_seen_stmt = select(
        _AuditLog.actor_user_id, func.max(_AuditLog.created_at).label("last_seen")
    ).where(
        _AuditLog.organization_id == org_id,
        _AuditLog.actor_user_id.is_not(None),
    )
    if active_within_days is not None:
        bounded = max(1, min(365, int(active_within_days)))
        cutoff = datetime.now(tz=UTC) - timedelta(days=bounded)
        last_seen_stmt = last_seen_stmt.where(_AuditLog.created_at >= cutoff)
    last_seen = last_seen_stmt.group_by(_AuditLog.actor_user_id).subquery()
    stmt = (
        select(User, last_seen.c.last_seen)
        .join(UserOrgMembership, UserOrgMembership.user_id == User.id)
        .outerjoin(last_seen, last_seen.c.actor_user_id == User.id)
        .where(
            UserOrgMembership.organization_id == org_id,
            User.deleted_at.is_(None),
        )
        .order_by(desc(last_seen.c.last_seen).nulls_last(), User.display_name)
        .limit(safe_limit)
    )
    if active_within_days is not None:
        stmt = stmt.where(last_seen.c.last_seen.is_not(None))
    rows = (await db.execute(stmt)).all()
    return [
        UserDTO(id=u.id, email=u.email, display_name=u.display_name, status=u.status)
        for u, _ in rows
    ]


@router.get("/v1/users", response_model=list[UserDTO])
async def list_users(
    _user: Annotated[CurrentUser, Depends(require_permission("manageUser"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
    status: str | None = None,
    q: str | None = None,
) -> list[UserDTO]:
    """List users that are members of the current org. Optional `status=
    <value>` scopes to one lifecycle (active/suspended/pending_invite);
    `q=<substring>` does a case-insensitive substring search across
    display_name and email."""
    stmt = (
        select(User)
        .join(UserOrgMembership, UserOrgMembership.user_id == User.id)
        .where(UserOrgMembership.organization_id == org_id, User.deleted_at.is_(None))
    )
    if status is not None:
        stmt = stmt.where(User.status == status)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where((User.display_name.ilike(like)) | (User.email.ilike(like)))
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
    """Create pending_invite user, bind to current org + profile, email invite link."""
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
    body_text = (
        f"Hi {body.display_name},\n\n"
        f"{user.user_id} has invited you to join Adhkar IR.\n\n"
        f"Accept your invite within 24 hours: {invite_link}\n"
    )
    await send_email(
        settings,
        to=body.email,
        subject="You're invited to Adhkar IR",
        body=body_text,
    )
    return UserDTO(
        id=new_user.id,
        email=new_user.email,
        display_name=new_user.display_name,
        status=new_user.status,
    )


class UserPatch(BaseModel):
    display_name: str | None = None
    profile_id: UUID | None = None  # in current org membership


@router.get("/v1/users/{user_id}", response_model=UserDTO)
async def get_user(
    user_id: UUID,
    _user: Annotated[CurrentUser, Depends(require_permission("viewCase"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserDTO:
    """Read one org-member by id. viewCase is enough since the response
    only exposes id/email/display_name/status — the assignee chip and
    comment author labels need this without inheriting manageUser."""
    row = (
        await db.execute(
            select(User)
            .join(UserOrgMembership, UserOrgMembership.user_id == User.id)
            .where(
                User.id == user_id,
                UserOrgMembership.organization_id == org_id,
                User.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user_not_found")
    return UserDTO(id=row.id, email=row.email, display_name=row.display_name, status=row.status)


@router.patch("/v1/users/{user_id}", response_model=UserDTO)
async def patch_user(
    user_id: UUID,
    body: UserPatch,
    _user: Annotated[CurrentUser, Depends(require_permission("manageUser"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserDTO:
    row = (
        await db.execute(select(User).where(User.id == user_id, User.deleted_at.is_(None)))
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user_not_found")
    if body.display_name is not None:
        row.display_name = body.display_name
    if body.profile_id is not None:
        mem = (
            await db.execute(
                select(UserOrgMembership).where(
                    UserOrgMembership.user_id == user_id,
                    UserOrgMembership.organization_id == org_id,
                )
            )
        ).scalar_one_or_none()
        if not mem:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "membership_not_found")
        profile = (
            await db.execute(
                select(Profile).where(
                    Profile.id == body.profile_id, Profile.organization_id == org_id
                )
            )
        ).scalar_one_or_none()
        if not profile:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "profile_not_in_org")
        mem.profile_id = profile.id
    await db.flush()
    return UserDTO(id=row.id, email=row.email, display_name=row.display_name, status=row.status)


@router.delete("/v1/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: UUID,
    user: Annotated[CurrentUser, Depends(require_permission("manageUser"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    if user_id == user.user_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "cannot_delete_self")
    row = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user_not_found")
    from datetime import UTC
    from datetime import datetime as _dt

    row.deleted_at = _dt.now(tz=UTC)
    await db.flush()


@router.post("/v1/users/{user_id}/lock", response_model=UserDTO)
async def lock_user(
    user_id: UUID,
    _user: Annotated[CurrentUser, Depends(require_permission("manageUser"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserDTO:
    row = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user_not_found")
    row.status = "locked"
    await db.flush()
    return UserDTO(id=row.id, email=row.email, display_name=row.display_name, status=row.status)


@router.post("/v1/users/{user_id}/unlock", response_model=UserDTO)
async def unlock_user(
    user_id: UUID,
    _user: Annotated[CurrentUser, Depends(require_permission("manageUser"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserDTO:
    row = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user_not_found")
    row.status = "active"
    await db.flush()
    return UserDTO(id=row.id, email=row.email, display_name=row.display_name, status=row.status)


@router.post("/v1/users/{user_id}/reset-mfa", status_code=status.HTTP_204_NO_CONTENT)
async def admin_reset_mfa(
    user_id: UUID,
    _user: Annotated[CurrentUser, Depends(require_permission("manageUser"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    from adhkar.db.models import MfaSecret

    row = (
        await db.execute(select(MfaSecret).where(MfaSecret.user_id == user_id))
    ).scalar_one_or_none()
    if row:
        await db.delete(row)
        await db.flush()


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
        body_text = (
            f"To reset your password, follow this link within 1 hour:\n\n{link}\n\n"
            "If you didn't request this, ignore this email."
        )
        await send_email(
            settings,
            to=user.email,
            subject="Adhkar IR — password reset",
            body=body_text,
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


class UserActivityRow(BaseModel):
    id: UUID
    created_at: datetime
    action: str
    entity_type: str
    entity_id: UUID | None


@router.get("/v1/users/{user_id}/recent-activity", response_model=list[UserActivityRow])
async def user_recent_activity(
    user_id: UUID,
    _user: Annotated[CurrentUser, Depends(require_permission("viewAudit"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 25,
    days: int | None = None,
    entity_type: str | None = None,
) -> list[UserActivityRow]:
    """Last N audit events authored by this user in the current org.
    Shortcut for the admin user-detail view; saves crafting an
    /v1/audit?actor_user_id=… URL by hand. Optional `days=N` (1..365)
    restricts the window to the last N days; `entity_type=<name>`
    scopes to one entity family (case/alert/task/observable/etc)."""
    from datetime import UTC as _UTC
    from datetime import datetime as _dt
    from datetime import timedelta as _td

    from sqlalchemy import desc as _desc

    from adhkar.db.models import AuditLog as _AuditLog

    safe_limit = max(1, min(200, int(limit)))
    stmt = (
        select(_AuditLog)
        .where(
            _AuditLog.organization_id == org_id,
            _AuditLog.actor_user_id == user_id,
        )
        .order_by(_desc(_AuditLog.created_at))
        .limit(safe_limit)
    )
    if days is not None:
        bounded = max(1, min(365, int(days)))
        cutoff = _dt.now(tz=_UTC) - _td(days=bounded)
        stmt = stmt.where(_AuditLog.created_at >= cutoff)
    if entity_type is not None:
        stmt = stmt.where(_AuditLog.entity_type == entity_type)
    rows = (await db.execute(stmt)).scalars().all()
    return [
        UserActivityRow(
            id=r.id,
            created_at=r.created_at,
            action=r.action,
            entity_type=r.entity_type,
            entity_id=r.entity_id,
        )
        for r in rows
    ]


@router.post("/v1/me/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_my_password(
    body: ChangePasswordRequest,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Self-service password change. Verifies current_password against the
    stored argon2 hash, applies the NIST + zxcvbn policy to new_password,
    persists the new hash, emits an audit event. 401 on wrong current,
    400 on policy fail, 409 when the account has no local password (SSO-only)."""
    user_row = (await db.execute(select(User).where(User.id == user.user_id))).scalar_one_or_none()
    if not user_row or user_row.password_hash is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "no_local_password")
    if not verify_password(body.current_password, user_row.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid_current_password")
    try:
        validate_password_policy(body.new_password)
    except Exception as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    user_row.password_hash = hash_password(body.new_password)
    await audit_and_emit(
        db,
        actor_user_id=user.user_id,
        organization_id=org_id,
        action="password_changed",
        entity_type="user",
        entity_id=user.user_id,
        diff={},
    )
