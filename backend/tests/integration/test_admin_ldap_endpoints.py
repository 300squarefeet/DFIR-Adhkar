"""Admin LDAP endpoints integration: CRUD + test-connection.

These tests exercise the real FastAPI app against a live Postgres + Redis
stack (via the session-scoped `services` fixture). No openldap container
is required here — the test-connection test exercises the unreachable-server
path which resolves without a real LDAP server.
"""

from __future__ import annotations

import asyncio

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


@pytest_asyncio.fixture
async def app_against_services(services, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", services["database_url"])
    monkeypatch.setenv("REDIS_URL", services["redis_url"])
    monkeypatch.setenv("ADHKAR_SECRET_KEY", "x" * 32)
    from adhkar.core.settings import Settings, get_settings

    get_settings.cache_clear()

    from alembic import command
    from alembic.config import Config

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", services["database_url"])
    await asyncio.to_thread(command.upgrade, cfg, "head")

    from adhkar.main import create_app

    return create_app(Settings())


async def _bootstrap_admin(services: dict, perms: list[str]) -> str:
    """Seed an org + admin user directly via the model layer. Returns an access token."""
    from adhkar.auth.password import hash_password
    from adhkar.auth.tokens import issue_tokens
    from adhkar.db.models import Organization, Profile, User, UserOrgMembership

    engine = create_async_engine(services["database_url"])
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as s:
            org = Organization(name="Admin LDAP Org", slug="admin-ldap")
            s.add(org)
            await s.flush()
            profile = Profile(organization_id=org.id, name="Admin", permissions=perms)
            s.add(profile)
            await s.flush()
            u = User(
                email="admin-ldap@example.test",
                display_name="Admin LDAP",
                password_hash=hash_password("Sufficient-pw-123"),
                status="active",
                default_org_id=org.id,
            )
            s.add(u)
            await s.flush()
            s.add(
                UserOrgMembership(
                    user_id=u.id,
                    organization_id=org.id,
                    profile_id=profile.id,
                    source="manual",
                )
            )
            tokens = await issue_tokens(
                session=s,
                user_id=u.id,
                org_id=org.id,
                perms=perms,
                secret="x" * 32,
            )
            await s.commit()
            return tokens.access_token
    finally:
        await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_admin_create_and_get_provider(app_against_services, services) -> None:
    """POST /v1/admin/ldap-providers creates a provider; GET retrieves it by ID.
    bind_password must not appear in either response."""
    token = await _bootstrap_admin(services, ["manageConfig"])
    headers = {"Authorization": f"Bearer {token}"}
    transport = ASGITransport(app=app_against_services)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.post(
            "/v1/admin/ldap-providers",
            headers=headers,
            json={
                "name": "p1",
                "server_uris": ["ldaps://dc01:636"],
                "bind_dn": "cn=svc,dc=corp,dc=com",
                "bind_password": "secretpw",
                "base_dn": "dc=corp,dc=com",
                "user_search_filter": "(mail={input})",
            },
        )
        assert r.status_code == 201, r.text
        body = r.json()
        # Sensitive fields must be scrubbed from response.
        assert "bind_password" not in body
        assert "bind_password_enc" not in body
        pid = body["id"]

        r2 = await c.get(f"/v1/admin/ldap-providers/{pid}", headers=headers)
        assert r2.status_code == 200
        assert r2.json()["name"] == "p1"
        assert "bind_password" not in r2.json()
        assert "bind_password_enc" not in r2.json()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_test_connection_against_unreachable_server(app_against_services, services) -> None:
    """POST /v1/admin/ldap-providers/{id}/test-connection returns ok=False for
    an unreachable server, with status 200 (the endpoint itself succeeded)."""
    token = await _bootstrap_admin(services, ["manageConfig"])
    headers = {"Authorization": f"Bearer {token}"}
    transport = ASGITransport(app=app_against_services)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.post(
            "/v1/admin/ldap-providers",
            headers=headers,
            json={
                "name": "unreachable",
                "server_uris": ["ldaps://nowhere.invalid:636"],
                "bind_dn": "cn=svc,dc=corp,dc=com",
                "bind_password": "x",
                "base_dn": "dc=corp,dc=com",
                "user_search_filter": "(mail={input})",
                "timeout_seconds": 2,
            },
        )
        assert r.status_code == 201, r.text
        pid = r.json()["id"]

        r2 = await c.post(
            f"/v1/admin/ldap-providers/{pid}/test-connection",
            headers=headers,
        )
        assert r2.status_code == 200, r2.text
        assert r2.json()["ok"] is False
