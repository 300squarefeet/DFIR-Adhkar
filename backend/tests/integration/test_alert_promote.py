"""Integration: ingest alert -> promote to case -> verify wiring."""

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


async def _bootstrap_user(services, perms: list[str]) -> str:
    from adhkar.auth.password import hash_password
    from adhkar.auth.tokens import issue_tokens
    from adhkar.db.models import Organization, Profile, User, UserOrgMembership
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    engine = create_async_engine(services["database_url"])
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as s:
            org = Organization(name="Alert Promote Org", slug="alert-promote")
            s.add(org)
            await s.flush()
            profile = Profile(organization_id=org.id, name="Admin", permissions=perms)
            s.add(profile)
            await s.flush()
            u = User(
                email="alert-promote@example.test",
                display_name="Alert Promote Tester",
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
async def test_alert_promote_creates_case_and_links_alert(app_against_services, services) -> None:
    token = await _bootstrap_user(services, ["manageAlert", "viewAlert", "manageCase", "viewCase"])
    headers = {"Authorization": f"Bearer {token}"}
    transport = ASGITransport(app=app_against_services)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.post(
            "/v1/alerts",
            json={
                "type": "external",
                "source": "siem-test",
                "source_ref": "alert-1",
                "title": "Suspicious login",
                "severity": 3,
                "tlp": "amber",
            },
            headers=headers,
        )
        assert r.status_code == 201, r.text
        alert_id = r.json()["id"]

        # Promote: route returns 201 with {case_id, case_number, alert_id}.
        r = await c.post(
            f"/v1/alerts/{alert_id}/promote",
            json={},
            headers=headers,
        )
        assert r.status_code == 201, r.text
        body = r.json()
        case_id = body["case_id"]
        assert case_id

        # Confirm alert.case_id is set via the alerts list with ?case_id filter (RC250).
        r = await c.get(f"/v1/alerts?case_id={case_id}", headers=headers)
        assert r.status_code == 200
        ids = [a["id"] for a in r.json()]
        assert alert_id in ids
