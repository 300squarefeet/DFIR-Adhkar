"""Shared session-scoped pg+redis+minio docker stack for integration tests.

Each test file consumes the `services` fixture and receives a dict of
URLs. Tests apply Alembic migrations at test setup time and roll back
per-test changes via savepoints (handled inside each test file).

In CI the fixture honors DATABASE_URL/REDIS_URL service-container env
vars and skips the docker boot. Local runs require Docker; missing
docker triggers pytest.skip, not test failure."""

from __future__ import annotations

import os

import pytest

DOCKER_AVAILABLE = os.environ.get("DOCKER_HOST") or os.path.exists("/var/run/docker.sock")
USE_SERVICES_FROM_ENV = bool(
    os.environ.get("DATABASE_URL") and os.environ.get("REDIS_URL") and not DOCKER_AVAILABLE
)


@pytest.fixture(scope="session")
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
