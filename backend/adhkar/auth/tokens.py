"""Access + refresh token issuance, rotation, and Redis-backed denylist."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import redis.asyncio as redis_async
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from adhkar.auth.jwt import JwtClaims, decode_jwt, encode_jwt
from adhkar.db.models import Session as SessionRow

ACCESS_TTL = timedelta(minutes=15)
REFRESH_TTL = timedelta(days=14)

_DENYLIST_PREFIX = "adhkar:denyjti:"


@dataclass(frozen=True, slots=True)
class IssuedTokens:
    access_token: str
    access_claims: JwtClaims
    refresh_token: str
    refresh_claims: JwtClaims


async def issue_tokens(
    *,
    session: AsyncSession,
    user_id: UUID,
    org_id: UUID | None,
    perms: list[str],
    secret: str,
    user_agent: str | None = None,
    ip: str | None = None,
) -> IssuedTokens:
    """Issue a fresh access + refresh pair and persist the refresh JTI row."""
    refresh_jti = uuid4()
    now = datetime.now(tz=UTC)
    refresh_expires = now + REFRESH_TTL

    access_token, access_claims = encode_jwt(
        secret=secret,
        user_id=user_id,
        typ="access",
        ttl=ACCESS_TTL,
        org_id=org_id,
        perms=perms,
    )
    refresh_token, refresh_claims = encode_jwt(
        secret=secret,
        user_id=user_id,
        typ="refresh",
        ttl=REFRESH_TTL,
        org_id=org_id,
        perms=[],  # refresh holds no perms; access is the carrier
        jti=refresh_jti,
    )

    session.add(
        SessionRow(
            id=refresh_jti,
            user_id=user_id,
            issued_at=now,
            expires_at=refresh_expires,
            last_seen_at=now,
            user_agent=(user_agent or "")[:200] or None,
            ip=ip,
        )
    )
    await session.flush()
    return IssuedTokens(
        access_token=access_token,
        access_claims=access_claims,
        refresh_token=refresh_token,
        refresh_claims=refresh_claims,
    )


async def rotate_refresh(
    *,
    session: AsyncSession,
    redis: redis_async.Redis,  # type: ignore[type-arg]
    refresh_token: str,
    perms: list[str],
    secret: str,
    user_agent: str | None = None,
    ip: str | None = None,
) -> IssuedTokens:
    """Verify + rotate: revoke old session, issue new pair."""
    old_claims = decode_jwt(refresh_token, secret=secret)
    if old_claims.typ != "refresh":
        raise ValueError("not_a_refresh_token")

    if await is_denied(redis, old_claims.jti):
        raise ValueError("refresh_revoked")

    now = datetime.now(tz=UTC)

    revoke_stmt = (
        update(SessionRow)
        .where(SessionRow.id == UUID(old_claims.jti), SessionRow.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    result = await session.execute(revoke_stmt)
    if result.rowcount == 0:  # type: ignore[attr-defined]
        raise ValueError("refresh_revoked")

    return await issue_tokens(
        session=session,
        user_id=old_claims.user_id,
        org_id=old_claims.org_uuid,
        perms=perms,
        secret=secret,
        user_agent=user_agent,
        ip=ip,
    )


async def revoke_session(
    *,
    session: AsyncSession,
    redis: redis_async.Redis,  # type: ignore[type-arg]
    jti: str,
    expires_at: datetime | None,
) -> None:
    """Mark the SessionRow revoked AND add JTI to Redis denylist with remaining TTL."""
    now = datetime.now(tz=UTC)
    await session.execute(
        update(SessionRow)
        .where(SessionRow.id == UUID(jti), SessionRow.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    if expires_at and expires_at > now:
        ttl = int((expires_at - now).total_seconds())
        if ttl > 0:
            await redis.setex(f"{_DENYLIST_PREFIX}{jti}", ttl, "1")


async def is_denied(redis: redis_async.Redis, jti: str) -> bool:  # type: ignore[type-arg]
    return await redis.exists(f"{_DENYLIST_PREFIX}{jti}") > 0
