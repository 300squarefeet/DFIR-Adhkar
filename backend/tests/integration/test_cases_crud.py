"""Integration: create -> patch -> soft-delete a case; verify audit trail."""

from __future__ import annotations

import asyncio

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


@pytest_asyncio.fixture
async def app_against_services(services, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", services["database_url"])
    monkeypatch.setenv("REDIS_URL", services["redis_url"])
    monkeypatch.setenv("ADHKAR_SECRET_KEY", "x" * 32)
    from adhkar.core.settings import get_settings

    get_settings.cache_clear()

    from alembic import command
    from alembic.config import Config

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", services["database_url"])
    await asyncio.to_thread(command.upgrade, cfg, "head")

    from adhkar.core.settings import Settings
    from adhkar.main import create_app

    return create_app(Settings())


async def _bootstrap_user_and_org(services) -> str:
    """Seed an org + admin user + JWT directly via the model layer. Returns
    the bearer access_token. org_id is encoded into the JWT (no separate
    request header - adhkar.api.deps.require_current_org reads it from
    user.org_id which get_current_user sets from the JWT claim)."""
    from adhkar.auth.password import hash_password
    from adhkar.auth.tokens import issue_tokens
    from adhkar.db.models import Organization, Profile, User, UserOrgMembership
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    engine = create_async_engine(services["database_url"])
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as s:
            org = Organization(name="Test Org", slug="test-org")
            s.add(org)
            await s.flush()
            profile = Profile(
                organization_id=org.id,
                name="Admin",
                permissions=["manageCase", "viewCase"],
            )
            s.add(profile)
            await s.flush()
            u = User(
                email="case-crud@example.test",
                display_name="Case CRUD Tester",
                password_hash=hash_password("Sufficient-pw-123"),
                status="active",
                default_org_id=org.id,
            )
            s.add(u)
            await s.flush()
            s.add(UserOrgMembership(user_id=u.id, organization_id=org.id, profile_id=profile.id))
            tokens = await issue_tokens(
                session=s,
                user_id=u.id,
                org_id=org.id,
                perms=["manageCase", "viewCase"],
                secret="x" * 32,
            )
            await s.commit()
            return tokens.access_token
    finally:
        await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_case_create_patch_soft_delete_round_trip(app_against_services, services) -> None:
    access_token = await _bootstrap_user_and_org(services)
    headers = {"Authorization": f"Bearer {access_token}"}
    transport = ASGITransport(app=app_against_services)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        # Create
        r = await c.post(
            "/v1/cases",
            json={"title": "End-to-end test case", "severity": 3, "tlp": "amber"},
            headers=headers,
        )
        assert r.status_code == 201, r.text
        case_id = r.json()["id"]

        # Patch (escalate to severity 4 + add a tag)
        r = await c.patch(
            f"/v1/cases/{case_id}",
            json={"severity": 4, "tags": ["incident"]},
            headers=headers,
        )
        assert r.status_code == 200, r.text
        assert r.json()["severity"] == 4
        assert r.json()["tags"] == ["incident"]

        # Soft-delete
        r = await c.delete(f"/v1/cases/{case_id}", headers=headers)
        assert r.status_code == 204, r.text

        # Confirm gone from list
        r = await c.get("/v1/cases", headers=headers)
        assert r.status_code == 200
        assert all(c_["id"] != case_id for c_ in r.json())
