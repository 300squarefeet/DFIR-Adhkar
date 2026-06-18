"""Shared session-scoped pg+redis+minio docker stack for integration tests.

Each test file consumes the `services` fixture and receives a dict of URLs.
A function-scoped autouse `_db_clean` fixture truncates all non-Alembic
tables between tests, so the session-shared database appears empty to each
test while only paying the container-boot cost once.

In CI the `services` fixture honors DATABASE_URL/REDIS_URL service-container
env vars and skips the docker boot. Local runs require Docker; missing
docker triggers pytest.skip, not test failure. (Env-var mode is ignored
when docker is also available — that's intentional, kept for explicit
local testing.)"""

from __future__ import annotations

import asyncio
import os
import subprocess
import time

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


@pytest.fixture(autouse=True)
def _db_clean(request):
    """Truncate every non-Alembic table between tests so the session-shared
    database appears empty per test. Skipped for tests that don't request the
    `services` fixture (cheap no-op for unit-style integration tests like the
    openapi smoke)."""
    # Only run when the test actually pulls services in (avoid forcing every
    # tests/integration/ test through the docker fixture).
    if "services" not in request.fixturenames:
        yield
        return

    services = request.getfixturevalue("services")
    yield  # run test first

    # Post-test: TRUNCATE all user tables in one statement.
    async def _truncate() -> None:
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import create_async_engine

        engine = create_async_engine(services["database_url"])
        try:
            async with engine.connect() as conn:
                # Discover all tables in public schema except alembic_version.
                rows = (
                    await conn.execute(
                        text(
                            "SELECT tablename FROM pg_tables "
                            "WHERE schemaname = 'public' AND tablename != 'alembic_version'"
                        )
                    )
                ).fetchall()
                if rows:
                    names = ", ".join(f'"{r[0]}"' for r in rows)
                    await conn.execute(text(f"TRUNCATE TABLE {names} RESTART IDENTITY CASCADE"))
                    await conn.commit()
        finally:
            await engine.dispose()

    asyncio.run(_truncate())


@pytest.fixture(scope="session")
def openldap_container():
    """Session-scoped osixia/openldap:1.5.0 container seeded with 3 users + 2 groups.

    Notes:
    - bitnami/openldap:2.6 is no longer available on Docker Hub; osixia/openldap:1.5.0
      is used instead (OpenLDAP 2.4.57, ships memberOf overlay pre-installed).
    - The memberOf overlay defaults to groupOfUniqueNames/uniqueMember. We reconfigure
      it for groupOfNames/member BEFORE adding data so that memberOf is populated.
    - The admin DN is used as bind DN because the svc account has no read ACL
      in osixia's default configuration (olcAccess gives "by * none").
    - LDAP data is seeded by copying the LDIF file into the container and running
      ldapadd; memberOf attributes are populated automatically by the overlay when
      groups are added.
    """
    if not DOCKER_AVAILABLE:
        pytest.skip("docker not available")

    from pathlib import Path

    from testcontainers.core.generic import DockerContainer
    from testcontainers.core.waiting_utils import wait_for_logs

    ldif = Path(__file__).parent / "fixtures" / "seed.ldif"

    container = (
        DockerContainer("osixia/openldap:1.5.0")
        .with_env("LDAP_ORGANISATION", "Corp")
        .with_env("LDAP_DOMAIN", "corp.com")
        .with_env("LDAP_ADMIN_PASSWORD", "adminpw")
        .with_env("LDAP_TLS", "false")
        .with_exposed_ports(389)
    )
    container.start()
    try:
        # Wait until slapd is up and answering.
        wait_for_logs(container, "slapd starting", timeout=60)
        # Give slapd a moment to finish initialising after the log line.
        time.sleep(2)

        cid = container.get_wrapped_container().id

        # ------------------------------------------------------------------
        # Reconfigure memberOf overlay to track groupOfNames / member
        # (osixia default is groupOfUniqueNames / uniqueMember).
        # This MUST happen before data is loaded so memberOf is populated.
        # ------------------------------------------------------------------
        _exec_ldap(
            cid,
            "ldapmodify -x -H ldap://localhost:389 -D 'cn=admin,cn=config' -w 'config'",
            stdin=(
                "dn: olcOverlay={0}memberof,olcDatabase={1}mdb,cn=config\n"
                "changetype: modify\n"
                "replace: olcMemberOfGroupOC\n"
                "olcMemberOfGroupOC: groupOfNames\n"
                "-\n"
                "replace: olcMemberOfMemberAD\n"
                "olcMemberOfMemberAD: member\n"
            ),
        )

        # ------------------------------------------------------------------
        # Copy the LDIF into the container and seed the directory.
        # ------------------------------------------------------------------
        subprocess.run(
            ["docker", "cp", str(ldif), f"{cid}:/tmp/seed.ldif"],
            check=True,
            capture_output=True,
        )
        _exec_ldap(
            cid,
            "ldapadd -x -H ldap://localhost:389"
            " -D 'cn=admin,dc=corp,dc=com' -w 'adminpw' -f /tmp/seed.ldif",
        )

        host = container.get_container_host_ip()
        port = container.get_exposed_port(389)
        yield {
            "uri": f"ldap://{host}:{port}",
            # osixia default ACLs deny non-admin reads; use admin as bind DN.
            "bind_dn": "cn=admin,dc=corp,dc=com",
            "bind_pw": "adminpw",
        }
    finally:
        container.stop()


def _exec_ldap(cid: str, cmd: str, stdin: str | None = None) -> None:
    """Run cmd inside the container via 'docker exec'. Raises on non-zero exit."""
    if stdin is not None:
        # Pipe stdin via bash -c so heredoc-style input works.
        full_cmd = ["docker", "exec", "-i", cid, "bash", "-c", cmd]
        result = subprocess.run(
            full_cmd,
            input=stdin.encode(),
            capture_output=True,
        )
    else:
        full_cmd = ["docker", "exec", cid, "bash", "-c", cmd]
        result = subprocess.run(full_cmd, capture_output=True)

    if result.returncode not in (0, 68):  # 68 = entry already exists (ldapadd)
        raise RuntimeError(
            f"ldap command failed (rc={result.returncode}):\n"
            f"  cmd: {cmd}\n"
            f"  stdout: {result.stdout.decode(errors='replace')}\n"
            f"  stderr: {result.stderr.decode(errors='replace')}"
        )
