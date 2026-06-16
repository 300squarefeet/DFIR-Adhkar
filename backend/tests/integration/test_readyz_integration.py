"""Integration test: spin real pg+redis+minio (via testcontainers), assert /readyz green.

Marked with @pytest.mark.integration so it can be skipped locally without docker.
CI runs it as part of the 'integration' job using GH service containers.
"""

import asyncio
import os

import pytest
from httpx import ASGITransport, AsyncClient

# Skip if no DOCKER_HOST is accessible; CI sets DATABASE_URL/REDIS_URL via service containers.
DOCKER_AVAILABLE = os.environ.get("DOCKER_HOST") or os.path.exists("/var/run/docker.sock")
USE_SERVICES_FROM_ENV = bool(
    os.environ.get("DATABASE_URL") and os.environ.get("REDIS_URL") and not DOCKER_AVAILABLE
)


@pytest.fixture(scope="module")
def services():
    if USE_SERVICES_FROM_ENV:
        yield {
            "database_url": os.environ["DATABASE_URL"],
            "redis_url": os.environ["REDIS_URL"],
            "s3_endpoint": os.environ.get("ADHKAR_S3_ENDPOINT", "http://localhost:9000"),
            "s3_access_key": os.environ.get("ADHKAR_S3_ACCESS_KEY", "minio-dev"),
            "s3_secret_key": os.environ.get("ADHKAR_S3_SECRET_KEY", "minio-dev-secret"),
        }
        return

    if not DOCKER_AVAILABLE:
        pytest.skip("docker not available; set DATABASE_URL/REDIS_URL for service-mode")

    from testcontainers.minio import MinioContainer
    from testcontainers.postgres import PostgresContainer
    from testcontainers.redis import RedisContainer

    pg = PostgresContainer("pgvector/pgvector:pg16")
    rd = RedisContainer("redis:7-alpine")
    s3 = MinioContainer("minio/minio:latest")
    pg.start()
    rd.start()
    s3.start()
    try:
        yield {
            "database_url": pg.get_connection_url().replace(
                "postgresql+psycopg2://", "postgresql+asyncpg://"
            ),
            "redis_url": f"redis://{rd.get_container_host_ip()}:{rd.get_exposed_port(6379)}/0",
            "s3_endpoint": f"http://{s3.get_container_host_ip()}:{s3.get_exposed_port(9000)}",
            "s3_access_key": s3.access_key,
            "s3_secret_key": s3.secret_key,
        }
    finally:
        pg.stop()
        rd.stop()
        s3.stop()


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
