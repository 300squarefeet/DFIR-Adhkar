"""Integration: create observable -> attach to case -> detach (round-trip)."""

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


async def _bootstrap(services, perms: list[str]) -> str:
    from adhkar.auth.password import hash_password
    from adhkar.auth.tokens import issue_tokens
    from adhkar.db.models import Organization, Profile, User, UserOrgMembership
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    engine = create_async_engine(services["database_url"])
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as s:
            org = Organization(name="Obs Attach Org", slug="obs-attach")
            s.add(org)
            await s.flush()
            profile = Profile(organization_id=org.id, name="Admin", permissions=perms)
            s.add(profile)
            await s.flush()
            u = User(
                email="obs-attach@example.test",
                display_name="Obs Attach Tester",
                password_hash=hash_password("Sufficient-pw-123"),
                status="active",
                default_org_id=org.id,
            )
            s.add(u)
            await s.flush()
            s.add(UserOrgMembership(user_id=u.id, organization_id=org.id, profile_id=profile.id))
            tokens = await issue_tokens(
                session=s, user_id=u.id, org_id=org.id, perms=perms, secret="x" * 32
            )
            await s.commit()
            return tokens.access_token
    finally:
        await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_observable_attach_detach_round_trip(app_against_services, services) -> None:
    token = await _bootstrap(
        services, ["manageCase", "viewCase", "manageObservable", "viewObservable"]
    )
    headers = {"Authorization": f"Bearer {token}"}
    transport = ASGITransport(app=app_against_services)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        # Create case
        r = await c.post(
            "/v1/cases",
            json={"title": "Obs round-trip", "severity": 2, "tlp": "amber"},
            headers=headers,
        )
        assert r.status_code == 201, r.text
        case_id = r.json()["id"]

        # Create observable (unattached)
        r = await c.post(
            "/v1/observables",
            json={"data_type": "ip", "data": "203.0.113.7", "tlp": "amber", "is_ioc": True},
            headers=headers,
        )
        assert r.status_code == 201, r.text
        obs_id = r.json()["id"]

        # Attach
        r = await c.post(
            f"/v1/cases/{case_id}/observables/attach",
            json={"observable_ids": [obs_id]},
            headers=headers,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["attached"] == 1

        # Confirm via per-case list
        r = await c.get(f"/v1/cases/{case_id}/observables", headers=headers)
        assert r.status_code == 200
        assert obs_id in [o["id"] for o in r.json()]

        # Detach
        r = await c.post(
            f"/v1/cases/{case_id}/observables/{obs_id}/detach",
            headers=headers,
        )
        assert r.status_code == 204, r.text

        # Confirm no longer on the case
        r = await c.get(f"/v1/cases/{case_id}/observables", headers=headers)
        assert r.status_code == 200
        assert obs_id not in [o["id"] for o in r.json()]
