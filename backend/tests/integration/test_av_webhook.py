"""AV scan webhook smoke tests (auth + signature, no DB writes)."""

from __future__ import annotations

import hashlib
import hmac

import pytest
from adhkar.core.settings import Settings
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def settings(monkeypatch):
    monkeypatch.setenv("ADHKAR_SECRET_KEY", "x" * 32)
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h/db")
    monkeypatch.setenv("REDIS_URL", "redis://h:6379/0")
    monkeypatch.setenv("ADHKAR_AV_WEBHOOK_SECRET", "test-secret-123")
    from adhkar.core.settings import get_settings

    get_settings.cache_clear()
    return Settings()


def _sig(secret: str, target: str, verdict: str) -> str:
    return hmac.new(
        secret.encode("utf-8"),
        f"{target}|{verdict}".encode(),
        hashlib.sha256,
    ).hexdigest()


@pytest.mark.asyncio
async def test_av_webhook_rejects_missing_signature(settings):
    from adhkar.main import create_app

    app = create_app(settings)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.post(
            "/v1/attachments/av-scan-webhook",
            json={"storage_key": "k/abc", "verdict": "clean"},
        )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_av_webhook_rejects_wrong_signature(settings):
    from adhkar.main import create_app

    app = create_app(settings)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.post(
            "/v1/attachments/av-scan-webhook",
            json={"storage_key": "k/abc", "verdict": "clean"},
            headers={"X-Adhkar-Signature": "deadbeef" * 8},
        )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_av_webhook_rejects_when_both_id_and_key_missing(settings):
    from adhkar.main import create_app

    app = create_app(settings)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.post(
            "/v1/attachments/av-scan-webhook",
            json={"verdict": "clean"},
            headers={"X-Adhkar-Signature": _sig("test-secret-123", "", "clean")},
        )
    # signature validates against "" target, but body validation catches it first
    assert r.status_code in (400, 422)


@pytest.mark.asyncio
async def test_av_webhook_disabled_when_secret_empty(monkeypatch):
    monkeypatch.setenv("ADHKAR_SECRET_KEY", "x" * 32)
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h/db")
    monkeypatch.setenv("REDIS_URL", "redis://h:6379/0")
    monkeypatch.setenv("ADHKAR_AV_WEBHOOK_SECRET", "")
    from adhkar.core.settings import Settings, get_settings

    get_settings.cache_clear()
    from adhkar.main import create_app

    app = create_app(Settings())
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.post(
            "/v1/attachments/av-scan-webhook",
            json={"storage_key": "k/abc", "verdict": "clean"},
            headers={"X-Adhkar-Signature": "anything"},
        )
    assert r.status_code == 503
