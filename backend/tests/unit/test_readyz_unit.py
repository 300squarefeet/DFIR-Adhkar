from unittest.mock import AsyncMock, MagicMock

import pytest
from adhkar.api.deps import get_engine, get_redis, get_s3
from adhkar.api.v1.meta import router as meta_router
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("ADHKAR_SECRET_KEY", "x" * 32)
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h/db")
    monkeypatch.setenv("REDIS_URL", "redis://h:6379/0")
    a = FastAPI()
    a.include_router(meta_router)

    # mocked deps — engine: returns context manager whose execute works
    engine = MagicMock()
    conn = AsyncMock()
    conn.execute = AsyncMock()
    engine.connect.return_value.__aenter__ = AsyncMock(return_value=conn)
    engine.connect.return_value.__aexit__ = AsyncMock(return_value=None)

    redis = AsyncMock()
    redis.ping = AsyncMock(return_value=True)

    s3 = MagicMock()
    s3.head_bucket = MagicMock(return_value={"ResponseMetadata": {"HTTPStatusCode": 200}})

    a.dependency_overrides[get_engine] = lambda: engine
    a.dependency_overrides[get_redis] = lambda: redis
    a.dependency_overrides[get_s3] = lambda: s3
    return a, redis


@pytest.mark.asyncio
async def test_readyz_all_ok(app):
    a, _redis = app
    transport = ASGITransport(app=a)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.get("/readyz")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ready"
    assert body["checks"] == {"db": "ok", "redis": "ok", "s3": "ok"}


@pytest.mark.asyncio
async def test_readyz_503_when_redis_down(app):
    a, redis = app
    redis.ping = AsyncMock(side_effect=ConnectionError("boom"))
    transport = ASGITransport(app=a)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.get("/readyz")
    assert r.status_code == 503
    body = r.json()
    assert body["checks"]["redis"] == "down"
    assert body["checks"]["db"] == "ok"
