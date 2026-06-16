"""Token-bucket rate limit middleware backed by Redis.

Per-IP+route, configurable per route family. The bucket is naive but safe:
on each request we INCR a Redis key with TTL, and reject when count exceeds
the limit. For tighter precision later, switch to a sliding-window log."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Final

import redis.asyncio as redis_async
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

_log = logging.getLogger(__name__)

# Per-route-family limits: requests-per-window. window=60 seconds.
_DEFAULT_WINDOW_SECONDS: Final[int] = 60
_LIMITS: Final[dict[str, int]] = {
    "/v1/auth/login": 10,
    "/v1/auth/refresh": 30,
    "/v1/auth/mfa": 20,
    "/v1/users": 60,
    "default": 600,
}


def _route_bucket(path: str) -> tuple[str, int]:
    for prefix, limit in _LIMITS.items():
        if prefix == "default":
            continue
        if path.startswith(prefix):
            return prefix, limit
    return "default", _LIMITS["default"]


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rejects when a client exceeds N requests per minute on a given route family.

    Open-fail policy: if Redis is unreachable, requests pass through (we log
    a warning). This keeps the platform up during ops incidents rather than
    blocking SOC analysts because of an unrelated outage."""

    def __init__(self, app: object, redis_url: str) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._redis_url = redis_url
        self._redis: redis_async.Redis[str] | None = None

    async def _client(self) -> redis_async.Redis[str] | None:
        if self._redis is None:
            try:
                self._redis = redis_async.from_url(self._redis_url, decode_responses=True)
            except (redis_async.RedisError, OSError):
                _log.warning("rate_limit_redis_unavailable url=%s", self._redis_url)
                return None
        return self._redis

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        bucket, limit = _route_bucket(request.url.path)
        client = request.client.host if request.client else "unknown"
        key = f"rl:{bucket}:{client}"
        r = await self._client()
        if r is None:
            return await call_next(request)
        try:
            count = await r.incr(key)
            if count == 1:
                await r.expire(key, _DEFAULT_WINDOW_SECONDS)
            if count > limit:
                return JSONResponse(
                    status_code=429,
                    content={"error": "rate_limited", "limit": limit, "bucket": bucket},
                    headers={"Retry-After": str(_DEFAULT_WINDOW_SECONDS)},
                )
        except redis_async.RedisError:
            _log.warning("rate_limit_redis_error path=%s", request.url.path)
        return await call_next(request)
