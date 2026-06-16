"""Readiness checks for /readyz endpoint."""

from dataclasses import dataclass
from typing import Any, Protocol

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


@dataclass(frozen=True, slots=True)
class CheckResult:
    name: str
    ok: bool
    detail: str | None = None


class _RedisLike(Protocol):
    async def ping(self) -> bool: ...


async def check_db(engine: AsyncEngine) -> CheckResult:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return CheckResult(name="db", ok=True)
    except Exception as e:
        return CheckResult(name="db", ok=False, detail=str(e))


async def check_redis(client: _RedisLike) -> CheckResult:
    try:
        await client.ping()
        return CheckResult(name="redis", ok=True)
    except Exception as e:
        return CheckResult(name="redis", ok=False, detail=str(e))


async def check_s3(client: Any, *, bucket: str) -> CheckResult:
    try:
        client.head_bucket(Bucket=bucket)
        return CheckResult(name="s3", ok=True)
    except Exception as e:
        return CheckResult(name="s3", ok=False, detail=str(e))
