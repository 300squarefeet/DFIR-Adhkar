"""Integration: endpoint + rule + event -> NotificationDelivery succeeded."""

from __future__ import annotations

import asyncio

import pytest
import pytest_asyncio
import respx
from httpx import ASGITransport, AsyncClient, Response


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
            org = Organization(name="Notify Org", slug="notify")
            s.add(org)
            await s.flush()
            profile = Profile(organization_id=org.id, name="Admin", permissions=perms)
            s.add(profile)
            await s.flush()
            u = User(
                email="notify@example.test",
                display_name="Notify Tester",
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
async def test_endpoint_test_button_records_succeeded_delivery(
    app_against_services, services
) -> None:
    """Endpoint Test button (RC88) fires a synthetic event through the dispatcher
    and writes a NotificationDelivery row. We mock the upstream webhook with respx."""
    token = await _bootstrap(services, ["manageConfig"])
    headers = {"Authorization": f"Bearer {token}"}
    transport = ASGITransport(app=app_against_services)

    with respx.mock:
        respx.post("https://hooks.example/webhook").mock(return_value=Response(200, text="ok"))

        async with AsyncClient(transport=transport, base_url="http://t") as c:
            r = await c.post(
                "/v1/notification-endpoints",
                json={
                    "name": "test-hook",
                    "kind": "webhook",
                    "config": {"url": "https://hooks.example/webhook"},
                    "enabled": True,
                },
                headers=headers,
            )
            assert r.status_code == 201, r.text
            endpoint_id = r.json()["id"]

            r = await c.post(
                f"/v1/notification-endpoints/{endpoint_id}/test",
                headers=headers,
            )
            assert r.status_code == 200, r.text
            assert r.json()["ok"] is True

    async with AsyncClient(transport=transport, base_url="http://t") as c2:
        r = await c2.get(
            f"/v1/notification-deliveries?endpoint_id={endpoint_id}",
            headers=headers,
        )
        assert r.status_code == 200
        deliveries = r.json()
        assert any(d["status"] == "succeeded" for d in deliveries)
