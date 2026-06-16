"""Meta endpoints: /healthz, /readyz, /version."""

import asyncio
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine

from adhkar import __version__
from adhkar.api.deps import get_engine, get_redis, get_s3, get_settings
from adhkar.core.settings import Settings
from adhkar.db.readiness import CheckResult, check_db, check_redis

router = APIRouter(tags=["meta"])


class HealthResponse(BaseModel):
    status: str


class VersionResponse(BaseModel):
    version: str
    commit: str
    # camelCase intentional: matches client-facing JSON convention (spec §5.3).
    builtAt: str  # noqa: N815


class ReadyResponse(BaseModel):
    status: str
    checks: dict[str, str]


@router.get("/healthz", response_model=HealthResponse)
async def healthz() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/version", response_model=VersionResponse)
async def version(s: Annotated[Settings, Depends(get_settings)]) -> VersionResponse:
    return VersionResponse(version=__version__, commit=s.git_commit, builtAt=s.built_at)


def _check_s3_sync(client: Any, *, bucket: str) -> CheckResult:
    """boto3's head_bucket is sync; wrap in asyncio.to_thread for /readyz."""
    try:
        client.head_bucket(Bucket=bucket)
        return CheckResult(name="s3", ok=True)
    except Exception as e:
        return CheckResult(name="s3", ok=False, detail=str(e))


@router.get(
    "/readyz",
    response_model=ReadyResponse,
    responses={503: {"model": ReadyResponse}},
)
async def readyz(
    response: Response,
    s: Annotated[Settings, Depends(get_settings)],
    engine: Annotated[AsyncEngine, Depends(get_engine)],
    redis: Annotated["Redis[str]", Depends(get_redis)],
    s3: Annotated[Any, Depends(get_s3)],
) -> ReadyResponse:
    results = await asyncio.gather(
        check_db(engine),
        check_redis(redis),
        asyncio.to_thread(_check_s3_sync, s3, bucket=s.s3_bucket),
        return_exceptions=False,
    )
    checks = {r.name: "ok" if r.ok else "down" for r in results}
    all_ok = all(r.ok for r in results)
    if not all_ok:
        response.status_code = 503
    return ReadyResponse(status="ready" if all_ok else "degraded", checks=checks)
