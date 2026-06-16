import pytest
from adhkar.api.v1.meta import router as meta_router
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def app():
    a = FastAPI()
    a.include_router(meta_router)
    return a


@pytest.mark.asyncio
async def test_healthz_returns_ok(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_version_returns_metadata(monkeypatch, app):
    monkeypatch.setenv("ADHKAR_SECRET_KEY", "x" * 32)
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h/db")
    monkeypatch.setenv("REDIS_URL", "redis://h:6379/0")
    monkeypatch.setenv("ADHKAR_GIT_COMMIT", "abc1234")
    monkeypatch.setenv("ADHKAR_BUILT_AT", "2026-06-16T10:42:00Z")
    # bust the lru_cache so the new env is picked up
    from adhkar.core.settings import get_settings

    get_settings.cache_clear()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.get("/version")
    assert r.status_code == 200
    body = r.json()
    assert body["version"] == "0.1.0.dev0"
    assert body["commit"] == "abc1234"
    assert body["builtAt"] == "2026-06-16T10:42:00Z"
