"""Integration test: spin real pg+redis+minio (via testcontainers), assert /readyz green.

Marked with @pytest.mark.integration so it can be skipped locally without docker.
CI runs it as part of the 'integration' job using GH service containers.
The shared `services` fixture lives in tests/integration/conftest.py.
"""

import asyncio

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.integration
@pytest.mark.asyncio
async def test_readyz_all_green_with_real_services(services, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", services["database_url"])
    monkeypatch.setenv("REDIS_URL", services["redis_url"])
    monkeypatch.setenv("ADHKAR_S3_ENDPOINT", services["s3_endpoint"])
    monkeypatch.setenv("ADHKAR_S3_ACCESS_KEY", services["s3_access_key"])
    monkeypatch.setenv("ADHKAR_S3_SECRET_KEY", services["s3_secret_key"])

    import boto3  # type: ignore[import-untyped]

    s3client = boto3.client(
        "s3",
        endpoint_url=services["s3_endpoint"],
        aws_access_key_id=services["s3_access_key"],
        aws_secret_access_key=services["s3_secret_key"],
        region_name="us-east-1",
    )
    try:
        s3client.create_bucket(Bucket="adhkar-attachments")
    except Exception:
        # bucket may already exist
        pass

    from alembic import command
    from alembic.config import Config

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", services["database_url"])
    await asyncio.to_thread(command.upgrade, cfg, "head")

    from adhkar.core.settings import Settings, get_settings

    get_settings.cache_clear()
    from adhkar.main import create_app

    settings = Settings()  # type: ignore[call-arg]
    app = create_app(settings)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.get("/readyz")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ready"
    assert body["checks"] == {"db": "ok", "redis": "ok", "s3": "ok"}
