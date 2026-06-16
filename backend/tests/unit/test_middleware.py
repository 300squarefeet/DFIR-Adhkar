import json

import pytest
from adhkar.core.logging import configure_logging
from adhkar.core.middleware import AccessLogMiddleware, RequestIdMiddleware
from adhkar.core.settings import Settings
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def settings(monkeypatch):
    monkeypatch.setenv("ADHKAR_SECRET_KEY", "x" * 32)
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h/db")
    monkeypatch.setenv("REDIS_URL", "redis://h:6379/0")
    return Settings()


@pytest.fixture
def app(settings):
    configure_logging(settings)
    a = FastAPI()
    a.add_middleware(AccessLogMiddleware)
    a.add_middleware(RequestIdMiddleware)

    @a.get("/ping")
    async def ping() -> dict[str, str]:
        return {"pong": "yes"}

    return a


@pytest.mark.asyncio
async def test_request_id_propagated_from_header(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/ping", headers={"X-Request-Id": "rid-abc"})
    assert r.status_code == 200
    assert r.headers["x-request-id"] == "rid-abc"


@pytest.mark.asyncio
async def test_request_id_generated_when_missing(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/ping")
    rid = r.headers["x-request-id"]
    # UUID4 format: 36 chars including hyphens
    assert len(rid) == 36
    assert rid.count("-") == 4


@pytest.mark.asyncio
async def test_access_log_emitted(app, capsys):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        await c.get("/ping", headers={"X-Request-Id": "rid-xyz"})
    out = capsys.readouterr().out.splitlines()
    payloads = [json.loads(line) for line in out if line.strip().startswith("{")]
    access = [p for p in payloads if p.get("event") == "http_request"]
    assert access, "no http_request log line emitted"
    assert access[-1]["request_id"] == "rid-xyz"
    assert access[-1]["method"] == "GET"
    assert access[-1]["path"] == "/ping"
    assert access[-1]["status"] == 200
    assert "duration_ms" in access[-1]
