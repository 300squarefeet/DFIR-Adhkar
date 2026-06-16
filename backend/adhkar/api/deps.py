"""FastAPI dependency providers."""

from typing import Annotated, Any

import boto3
import redis.asyncio as redis_async
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncEngine

from adhkar.core.settings import Settings
from adhkar.core.settings import get_settings as _get_settings
from adhkar.db.engine import create_engine


def get_settings(settings: Settings = Depends(_get_settings)) -> Settings:  # noqa: B008
    # Depends() in default position is FastAPI's canonical injection pattern.
    return settings


def get_engine(s: Annotated[Settings, Depends(get_settings)]) -> AsyncEngine:
    return create_engine(s)


def get_redis(s: Annotated[Settings, Depends(get_settings)]) -> "redis_async.Redis[str]":
    return redis_async.from_url(s.redis_url, decode_responses=True)


def get_s3(s: Annotated[Settings, Depends(get_settings)]) -> Any:
    return boto3.client(
        "s3",
        endpoint_url=s.s3_endpoint,
        aws_access_key_id=s.s3_access_key,
        aws_secret_access_key=s.s3_secret_key,
        region_name=s.s3_region,
    )
