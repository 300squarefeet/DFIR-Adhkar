"""API key endpoints: user-owned + admin."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from argon2 import PasswordHasher
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from adhkar.api.deps import CurrentUser, get_current_user, get_db, require_permission
from adhkar.auth.permissions import validate_permissions
from adhkar.db.models import ApiKey

router = APIRouter(tags=["api-keys"])

_hasher = PasswordHasher()
API_KEY_PREFIX = "adh_"
_PREFIX_INDEX_LEN = 12  # "adh_" + 8 random


class ApiKeyDTO(BaseModel):
    id: UUID
    label: str
    prefix: str
    scope_permissions: list[str]
    expires_at: datetime | None
    last_used_at: datetime | None
    created_at: datetime
    revoked_at: datetime | None


class CreateRequest(BaseModel):
    label: str
    scope_permissions: list[str]
    expires_at: datetime | None = None


class CreateResponse(BaseModel):
    api_key: ApiKeyDTO
    plain_token: str  # shown ONCE


def _generate_key() -> tuple[str, str]:
    body = secrets.token_hex(16)  # 32 chars
    full = f"{API_KEY_PREFIX}{body}"
    return full, full[:_PREFIX_INDEX_LEN]


def _to_dto(k: ApiKey) -> ApiKeyDTO:
    return ApiKeyDTO(
        id=k.id,
        label=k.label,
        prefix=k.prefix,
        scope_permissions=list(k.scope_permissions),
        expires_at=k.expires_at,
        last_used_at=k.last_used_at,
        created_at=k.created_at,
        revoked_at=k.revoked_at,
    )


@router.get("/v1/me/api-keys", response_model=list[ApiKeyDTO])
async def list_my_keys(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    include_revoked: bool = False,
    unused: bool | None = None,
) -> list[ApiKeyDTO]:
    """List the caller's API keys. `include_revoked=true` returns the
    full audit set (default hides revoked); `unused=true` keeps only
    keys whose last_used_at is null — useful for a key-cleanup nudge."""
    stmt = select(ApiKey).where(ApiKey.user_id == user.user_id)
    if not include_revoked:
        stmt = stmt.where(ApiKey.revoked_at.is_(None))
    if unused is True:
        stmt = stmt.where(ApiKey.last_used_at.is_(None))
    elif unused is False:
        stmt = stmt.where(ApiKey.last_used_at.is_not(None))
    rows = (await db.execute(stmt)).scalars().all()
    return [_to_dto(k) for k in rows]


@router.post("/v1/me/api-keys", response_model=CreateResponse, status_code=status.HTTP_201_CREATED)
async def create_my_key(
    body: CreateRequest,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CreateResponse:
    try:
        scope = validate_permissions(body.scope_permissions)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    # Scope must be subset of current user permissions
    bad = [p for p in scope if p not in user.permissions]
    if bad:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"scope_exceeds_user_permissions:{bad}")
    plain, prefix = _generate_key()
    row = ApiKey(
        user_id=user.user_id,
        label=body.label,
        prefix=prefix,
        key_hash=_hasher.hash(plain),
        scope_permissions=scope,
        expires_at=body.expires_at,
    )
    db.add(row)
    await db.flush()
    return CreateResponse(api_key=_to_dto(row), plain_token=plain)


@router.delete("/v1/me/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_my_key(
    key_id: UUID,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    row = (
        await db.execute(
            select(ApiKey).where(
                ApiKey.id == key_id, ApiKey.user_id == user.user_id, ApiKey.revoked_at.is_(None)
            )
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "api_key_not_found")
    row.revoked_at = datetime.now(tz=UTC)
    await db.flush()


@router.get("/v1/users/{user_id}/api-keys", response_model=list[ApiKeyDTO])
async def list_user_keys(
    user_id: UUID,
    _user: Annotated[CurrentUser, Depends(require_permission("manageApiKey"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[ApiKeyDTO]:
    rows = (await db.execute(select(ApiKey).where(ApiKey.user_id == user_id))).scalars().all()
    return [_to_dto(k) for k in rows]


@router.delete("/v1/users/{user_id}/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_revoke_key(
    user_id: UUID,
    key_id: UUID,
    _user: Annotated[CurrentUser, Depends(require_permission("manageApiKey"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    row = (
        await db.execute(
            select(ApiKey).where(
                ApiKey.id == key_id, ApiKey.user_id == user_id, ApiKey.revoked_at.is_(None)
            )
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "api_key_not_found")
    row.revoked_at = datetime.now(tz=UTC)
    await db.flush()
