"""Meta endpoints: /healthz, /readyz, /version."""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from adhkar import __version__
from adhkar.core.settings import Settings, get_settings

router = APIRouter(tags=["meta"])


class HealthResponse(BaseModel):
    status: str


class VersionResponse(BaseModel):
    version: str
    commit: str
    # camelCase intentional: matches client-facing JSON convention (spec §5.3).
    builtAt: str  # noqa: N815


@router.get("/healthz", response_model=HealthResponse)
async def healthz() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/version", response_model=VersionResponse)
async def version(s: Annotated[Settings, Depends(get_settings)]) -> VersionResponse:
    return VersionResponse(version=__version__, commit=s.git_commit, builtAt=s.built_at)
