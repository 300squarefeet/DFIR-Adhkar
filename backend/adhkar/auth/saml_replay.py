"""Redis-backed SAML assertion replay cache.

Stores each accepted assertion ID under `saml:seen:{id}` with TTL =
assertion's NotOnOrAfter - now (clamped to [1, 86400] seconds). A
second arrival inside the window is rejected via SamlReplayError by
the caller."""

from __future__ import annotations

import redis.asyncio as redis_async

_KEY_PREFIX = "saml:seen:"
_TTL_MIN = 1
_TTL_MAX = 86_400


async def mark_seen(
    redis: redis_async.Redis,  # type: ignore[type-arg]
    assertion_id: str,
    ttl_seconds: int,
) -> bool:
    """Atomic SET NX EX. Returns True on first sight, False on replay."""
    ttl = max(_TTL_MIN, min(_TTL_MAX, int(ttl_seconds)))
    key = f"{_KEY_PREFIX}{assertion_id}"
    result = await redis.set(key, "1", nx=True, ex=ttl)
    return bool(result)
