import pytest
from adhkar.core.settings import Settings
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def settings(monkeypatch):
    monkeypatch.setenv("ADHKAR_SECRET_KEY", "x" * 32)
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h/db")
    monkeypatch.setenv("REDIS_URL", "redis://h:6379/0")
    from adhkar.core.settings import get_settings

    get_settings.cache_clear()
    return Settings()


@pytest.mark.asyncio
async def test_factory_assembles_full_app(settings):
    from adhkar.main import create_app

    app = create_app(settings)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.get("/healthz")
        assert r.status_code == 200
        r2 = await c.get("/openapi.json")
        assert r2.status_code == 200
        spec = r2.json()
        assert spec["info"]["title"] == "Adhkar IR API"
        # request-id header round-trips
        r3 = await c.get("/healthz", headers={"X-Request-Id": "rid-test"})
        assert r3.headers["x-request-id"] == "rid-test"


@pytest.mark.asyncio
async def test_openapi_spec_is_valid(settings):
    from adhkar.main import create_app
    from openapi_spec_validator import validate

    app = create_app(settings)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.get("/openapi.json")
    spec = r.json()
    validate(spec)
