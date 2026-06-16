"""JWT encode/decode primitives + claims model."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from uuid import UUID, uuid4

import jwt

_ALG = "HS256"


@dataclass(frozen=True, slots=True)
class JwtClaims:
    """Decoded JWT payload, type-safe."""

    sub: str  # user_id
    org_id: str | None
    perms: tuple[str, ...]
    jti: str
    iat: int
    exp: int
    typ: Literal["access", "refresh"]

    @property
    def user_id(self) -> UUID:
        return UUID(self.sub)

    @property
    def org_uuid(self) -> UUID | None:
        return UUID(self.org_id) if self.org_id else None


def encode_jwt(
    *,
    secret: str,
    user_id: UUID,
    typ: Literal["access", "refresh"],
    ttl: timedelta,
    org_id: UUID | None,
    perms: list[str] | tuple[str, ...] = (),
    jti: UUID | None = None,
) -> tuple[str, JwtClaims]:
    """Encode a signed JWT and return (token, decoded_claims)."""
    now = datetime.now(tz=UTC)
    exp = now + ttl
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "org_id": str(org_id) if org_id else None,
        "perms": list(perms),
        "jti": str(jti or uuid4()),
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "typ": typ,
    }
    token = jwt.encode(payload, secret, algorithm=_ALG)
    claims = JwtClaims(
        sub=payload["sub"],
        org_id=payload["org_id"],
        perms=tuple(payload["perms"]),
        jti=payload["jti"],
        iat=payload["iat"],
        exp=payload["exp"],
        typ=typ,
    )
    return token, claims


def decode_jwt(token: str, *, secret: str) -> JwtClaims:
    """Decode and verify signature + expiry. Raises jwt.InvalidTokenError family on failure."""
    payload = jwt.decode(
        token,
        secret,
        algorithms=[_ALG],
        options={"require": ["sub", "jti", "iat", "exp", "typ"]},
    )
    return JwtClaims(
        sub=payload["sub"],
        org_id=payload.get("org_id"),
        perms=tuple(payload.get("perms", [])),
        jti=payload["jti"],
        iat=payload["iat"],
        exp=payload["exp"],
        typ=payload["typ"],
    )
