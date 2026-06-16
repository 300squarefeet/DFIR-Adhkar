"""FastAPI dependency providers."""

from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from typing import Annotated, Any
from uuid import UUID

import boto3  # type: ignore[import-untyped]
import jwt
import redis.asyncio as redis_async
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from adhkar.auth.jwt import JwtClaims, decode_jwt
from adhkar.auth.tokens import is_denied
from adhkar.core.settings import Settings
from adhkar.core.settings import get_settings as _get_settings
from adhkar.db.engine import create_engine


def get_settings(settings: Settings = Depends(_get_settings)) -> Settings:  # noqa: B008
    # Depends() in default position is FastAPI's canonical injection pattern.
    return settings


def get_engine(s: Annotated[Settings, Depends(get_settings)]) -> AsyncEngine:
    return create_engine(s)


def get_session_factory(
    engine: Annotated[AsyncEngine, Depends(get_engine)],
) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_db(
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> AsyncIterator[AsyncSession]:
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def get_redis(s: Annotated[Settings, Depends(get_settings)]) -> redis_async.Redis:  # type: ignore[type-arg]
    return redis_async.from_url(s.redis_url, decode_responses=True)


def get_s3(s: Annotated[Settings, Depends(get_settings)]) -> Any:
    return boto3.client(
        "s3",
        endpoint_url=s.s3_endpoint,
        aws_access_key_id=s.s3_access_key,
        aws_secret_access_key=s.s3_secret_key,
        region_name=s.s3_region,
    )


# ============================================================================
# Authentication
# ============================================================================


@dataclass(frozen=True, slots=True)
class CurrentUser:
    user_id: UUID
    org_id: UUID | None
    permissions: frozenset[str]
    claims: JwtClaims


def _extract_bearer(request: Request) -> str | None:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[len("Bearer ") :].strip() or None
    return None


async def get_current_user(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    redis: Annotated[redis_async.Redis, Depends(get_redis)],  # type: ignore[type-arg]
) -> CurrentUser:
    token = _extract_bearer(request)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing_token")

    # API-key Bearer (prefix "adh_") → lookup vs ApiKey table
    if token.startswith("adh_"):
        from datetime import UTC
        from datetime import datetime as _dt

        from argon2 import PasswordHasher
        from argon2.exceptions import VerifyMismatchError
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import async_sessionmaker

        from adhkar.auth.jwt import JwtClaims
        from adhkar.db.engine import create_engine
        from adhkar.db.models import ApiKey
        from adhkar.db.models import User as UserRow

        engine = create_engine(settings)
        sf = async_sessionmaker(engine, expire_on_commit=False)
        async with sf() as session:
            row = (
                await session.execute(
                    select(ApiKey).where(ApiKey.prefix == token[:12], ApiKey.revoked_at.is_(None))
                )
            ).scalar_one_or_none()
            if not row:
                raise HTTPException(status.HTTP_401_UNAUTHORIZED, "api_key_invalid")
            if row.expires_at and row.expires_at < _dt.now(tz=UTC):
                raise HTTPException(status.HTTP_401_UNAUTHORIZED, "api_key_expired")
            try:
                PasswordHasher().verify(row.key_hash, token)
            except VerifyMismatchError as e:
                raise HTTPException(status.HTTP_401_UNAUTHORIZED, "api_key_invalid") from e
            user_row = (
                await session.execute(select(UserRow).where(UserRow.id == row.user_id))
            ).scalar_one()
            row.last_used_at = _dt.now(tz=UTC)
            await session.commit()
        await engine.dispose()
        synthetic_claims = JwtClaims(
            sub=str(row.user_id),
            org_id=None,
            perms=tuple(row.scope_permissions),
            jti=f"apikey:{row.id}",
            iat=0,
            exp=0,
            typ="access",
        )
        return CurrentUser(
            user_id=row.user_id,
            org_id=user_row.default_org_id,
            permissions=frozenset(row.scope_permissions),
            claims=synthetic_claims,
        )

    try:
        claims = decode_jwt(token, secret=settings.secret_key)
    except jwt.ExpiredSignatureError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "token_expired") from e
    except jwt.InvalidTokenError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "token_invalid") from e
    if claims.typ != "access":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "wrong_token_type")
    if await is_denied(redis, claims.jti):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "token_revoked")
    return CurrentUser(
        user_id=claims.user_id,
        org_id=claims.org_uuid,
        permissions=frozenset(claims.perms),
        claims=claims,
    )


def require_permission(
    name: str,
) -> Callable[[CurrentUser], Awaitable[CurrentUser]]:
    """FastAPI dependency factory: 403 if current user lacks `name`."""

    async def _check(
        user: Annotated[CurrentUser, Depends(get_current_user)],
    ) -> CurrentUser:
        if name not in user.permissions:
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"missing_permission:{name}")
        return user

    return _check


async def require_current_org(
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> UUID:
    if user.org_id is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "no_current_org")
    return user.org_id
