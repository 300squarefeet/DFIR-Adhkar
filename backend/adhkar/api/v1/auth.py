"""Auth endpoints: /v1/auth/{login,logout,refresh,me,switch-org}."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID

import redis.asyncio as redis_async
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from adhkar.api.deps import CurrentUser, get_current_user, get_db, get_redis, get_settings
from adhkar.auth.password import verify_password
from adhkar.auth.tokens import ACCESS_TTL, REFRESH_TTL, issue_tokens, revoke_session, rotate_refresh
from adhkar.core.settings import Settings
from adhkar.db.models import Profile, User, UserOrgMembership

router = APIRouter(prefix="/v1/auth", tags=["auth"])

REFRESH_COOKIE = "adhkar_refresh"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    mfa_code: str | None = None


class LoginResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105 — OAuth 2 token_type literal
    expires_in: int
    user_id: UUID
    current_org_id: UUID | None


class MeResponse(BaseModel):
    user_id: UUID
    email: str
    display_name: str
    current_org_id: UUID | None
    permissions: list[str]
    memberships: list[MembershipDTO]


class MembershipDTO(BaseModel):
    org_id: UUID
    org_name: str
    profile_id: UUID
    profile_name: str


MeResponse.model_rebuild()


def _set_refresh_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=token,
        max_age=int(REFRESH_TTL.total_seconds()),
        httponly=True,
        secure=settings.env != "dev",
        samesite="strict",
        path="/v1/auth",
    )


@router.post("/login", response_model=LoginResponse)
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> LoginResponse:
    user = (await db.execute(select(User).where(User.email == body.email))).scalar_one_or_none()
    if not user or not user.password_hash:
        # Constant-ish: avoid email enumeration
        verify_password("$argon2id$v=19$m=65536,t=2,p=2$decoy$decoy", body.password)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid_credentials")
    if not verify_password(user.password_hash, body.password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid_credentials")
    if user.status == "pending_invite":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "invite_pending")
    if user.status == "locked":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "account_locked")

    memberships = (
        (await db.execute(select(UserOrgMembership).where(UserOrgMembership.user_id == user.id)))
        .scalars()
        .all()
    )
    if not memberships:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "no_organization")

    chosen = next(
        (m for m in memberships if m.organization_id == user.default_org_id),
        memberships[0],
    )

    profile = (
        await db.execute(select(Profile).where(Profile.id == chosen.profile_id))
    ).scalar_one()

    issued = await issue_tokens(
        session=db,
        user_id=user.id,
        org_id=chosen.organization_id,
        perms=sorted(profile.permissions),
        secret=settings.secret_key,
        user_agent=request.headers.get("user-agent"),
        ip=request.client.host if request.client else None,
    )

    _set_refresh_cookie(response, issued.refresh_token, settings)
    return LoginResponse(
        access_token=issued.access_token,
        expires_in=int(ACCESS_TTL.total_seconds()),
        user_id=user.id,
        current_org_id=chosen.organization_id,
    )


@router.post("/refresh", response_model=LoginResponse)
async def refresh(
    request: Request,
    response: Response,
    settings: Annotated[Settings, Depends(get_settings)],
    redis: Annotated[redis_async.Redis, Depends(get_redis)],  # type: ignore[type-arg]
    db: Annotated[AsyncSession, Depends(get_db)],
    refresh_cookie: Annotated[str | None, Cookie(alias=REFRESH_COOKIE)] = None,
) -> LoginResponse:
    if not refresh_cookie:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing_refresh")
    try:
        issued = await rotate_refresh(
            session=db,
            redis=redis,
            refresh_token=refresh_cookie,
            perms=[],
            secret=settings.secret_key,
            user_agent=request.headers.get("user-agent"),
            ip=request.client.host if request.client else None,
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(e)) from e
    _set_refresh_cookie(response, issued.refresh_token, settings)
    return LoginResponse(
        access_token=issued.access_token,
        expires_in=int(ACCESS_TTL.total_seconds()),
        user_id=issued.access_claims.user_id,
        current_org_id=issued.access_claims.org_uuid,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    redis: Annotated[redis_async.Redis, Depends(get_redis)],  # type: ignore[type-arg]
    db: Annotated[AsyncSession, Depends(get_db)],
    refresh_cookie: Annotated[str | None, Cookie(alias=REFRESH_COOKIE)] = None,
) -> Response:
    # Revoke current access token jti
    await revoke_session(
        session=db,
        redis=redis,
        jti=user.claims.jti,
        expires_at=datetime.fromtimestamp(user.claims.exp, tz=UTC),
    )
    if refresh_cookie:
        try:
            from adhkar.auth.jwt import decode_jwt

            refresh_claims = decode_jwt(refresh_cookie, secret="ignored-validation-only")
        except Exception:
            refresh_claims = None
        if refresh_claims is not None:
            await revoke_session(
                session=db,
                redis=redis,
                jti=refresh_claims.jti,
                expires_at=datetime.fromtimestamp(refresh_claims.exp, tz=UTC),
            )
    response.delete_cookie(REFRESH_COOKIE, path="/v1/auth")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=MeResponse)
async def me(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MeResponse:
    db_user = (await db.execute(select(User).where(User.id == user.user_id))).scalar_one()
    memberships = (
        await db.execute(
            select(UserOrgMembership, Profile, User)
            .join(Profile, UserOrgMembership.profile_id == Profile.id)
            .where(UserOrgMembership.user_id == user.user_id)
        )
    ).all()
    # Also fetch org names
    from adhkar.db.models import Organization

    org_rows = (
        (
            await db.execute(
                select(Organization).where(
                    Organization.id.in_([m[0].organization_id for m in memberships])
                )
            )
        )
        .scalars()
        .all()
    )
    org_name_map = {o.id: o.name for o in org_rows}
    out = MeResponse(
        user_id=db_user.id,
        email=db_user.email,
        display_name=db_user.display_name,
        current_org_id=user.org_id,
        permissions=sorted(user.permissions),
        memberships=[
            MembershipDTO(
                org_id=m[0].organization_id,
                org_name=org_name_map.get(m[0].organization_id, "?"),
                profile_id=m[1].id,
                profile_name=m[1].name,
            )
            for m in memberships
        ],
    )
    return out
