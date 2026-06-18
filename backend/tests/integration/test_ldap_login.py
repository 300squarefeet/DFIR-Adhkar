"""End-to-end LDAP login: auto-provision, group sync, fail-closed.

Uses a session-scoped bitnami-equivalent openldap container (osixia/openldap:1.5.0)
seeded with 3 users + 2 groups. The memberOf overlay is configured for
groupOfNames/member so ldap_service.LdapAuthService can resolve groups via
the standard memberOf attribute without any code changes.
"""

from __future__ import annotations

import asyncio

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


@pytest_asyncio.fixture
async def app_and_provider(services, openldap_container, monkeypatch):
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

    from adhkar.auth.crypto import encrypt
    from adhkar.db.models import (
        LdapGroupMapping,
        LdapProvider,
        Organization,
        Profile,
    )

    engine = create_async_engine(services["database_url"])
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as s:
            org = Organization(name="LDAP SOC", slug="ldap-soc")
            s.add(org)
            await s.flush()
            analyst = Profile(
                organization_id=org.id,
                name="Analyst",
                permissions=["viewCase", "manageCase"],
            )
            s.add(analyst)
            await s.flush()
            enc = encrypt(openldap_container["bind_pw"].encode(), "x" * 32).decode()
            provider = LdapProvider(
                name="test-ldap",
                server_uris=[openldap_container["uri"]],
                bind_dn=openldap_container["bind_dn"],
                bind_password_enc=enc,
                base_dn="dc=corp,dc=com",
                user_search_filter=("(&(objectClass=inetOrgPerson)(|(mail={input})(cn={input})))"),
                # cn is a valid inetOrgPerson attribute (sAMAccountName is AD-only).
                user_id_attr="cn",
                user_email_attr="mail",
                user_display_name_attr="displayName",
                group_membership_attr="memberOf",
                tls_required=False,
                allow_insecure=True,
                enabled=True,
                priority=10,
                timeout_seconds=10,
            )
            s.add(provider)
            await s.flush()
            s.add(
                LdapGroupMapping(
                    ldap_provider_id=provider.id,
                    group_dn="cn=SOC Analysts,ou=groups,dc=corp,dc=com",
                    organization_id=org.id,
                    profile_id=analyst.id,
                )
            )
            await s.commit()
            provider_id = provider.id
            org_id = org.id
            analyst_id = analyst.id
    finally:
        await engine.dispose()

    from adhkar.main import create_app

    app = create_app(Settings())
    yield (
        app,
        {
            "provider_id": provider_id,
            "org_id": org_id,
            "analyst_id": analyst_id,
            "services": services,
        },
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_first_login_auto_provisions_user_and_membership(app_and_provider) -> None:
    app, ctx = app_and_provider
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.post(
            "/v1/auth/login",
            json={"email": "alice@corp.com", "password": "alice-pw"},
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["access_token"]
    assert body["current_org_id"] == str(ctx["org_id"])


@pytest.mark.integration
@pytest.mark.asyncio
async def test_wrong_password_returns_401(app_and_provider) -> None:
    from adhkar.db.models import User

    app, ctx = app_and_provider
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.post(
            "/v1/auth/login",
            json={"email": "alice@corp.com", "password": "wrong"},
        )
    assert r.status_code == 401

    engine = create_async_engine(ctx["services"]["database_url"])
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as s:
            user_row = (
                await s.execute(select(User).where(User.email == "alice@corp.com"))
            ).scalar_one_or_none()
            assert user_row is None, "wrong password must not provision a User row"
    finally:
        await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_unmapped_group_user_returns_403(app_and_provider) -> None:
    """mallory is in Marketing which has no LdapGroupMapping -> 403."""
    from adhkar.db.models import User

    app, ctx = app_and_provider
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.post(
            "/v1/auth/login",
            json={"email": "mallory@corp.com", "password": "mallory-pw"},
        )
    assert r.status_code == 403, r.text
    assert r.json()["detail"] == "ldap_no_authorized_group"

    engine = create_async_engine(ctx["services"]["database_url"])
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as s:
            user_row = (
                await s.execute(select(User).where(User.email == "mallory@corp.com"))
            ).scalar_one_or_none()
            assert user_row is None, "unmapped group must not provision a User row"
    finally:
        await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_returning_user_membership_diff_applied(app_and_provider) -> None:
    """First login provisions alice; deleting the mapping means second login is 403."""
    app, ctx = app_and_provider
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        # First login -> creates user with 1 LDAP membership
        r1 = await c.post(
            "/v1/auth/login",
            json={"email": "alice@corp.com", "password": "alice-pw"},
        )
        assert r1.status_code == 200, r1.text

        # Delete the mapping so on next login alice has no resolved memberships
        # AND no manual ones -> ldap_no_authorized_group -> 403.
        engine = create_async_engine(ctx["services"]["database_url"])
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        from adhkar.db.models import LdapGroupMapping

        async with session_factory() as s:
            res = await s.execute(select(LdapGroupMapping))
            for m in res.scalars().all():
                await s.delete(m)
            await s.commit()
        await engine.dispose()

        r2 = await c.post(
            "/v1/auth/login",
            json={"email": "alice@corp.com", "password": "alice-pw"},
        )
        assert r2.status_code == 403, r2.text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_manual_membership_preserved_on_ldap_sync(app_and_provider) -> None:
    """A manual membership survives even when no LDAP group mapping matches."""
    app, ctx = app_and_provider
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        # First login auto-provisions bob with one LDAP membership.
        r1 = await c.post(
            "/v1/auth/login",
            json={"email": "bob@corp.com", "password": "bob-pw"},
        )
        assert r1.status_code == 200, r1.text

        # Switch his LDAP membership to manual + drop the group mapping.
        engine = create_async_engine(ctx["services"]["database_url"])
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        from adhkar.db.models import LdapGroupMapping, User, UserOrgMembership

        async with session_factory() as s:
            bob = (await s.execute(select(User).where(User.email == "bob@corp.com"))).scalar_one()
            await s.execute(
                UserOrgMembership.__table__.update()
                .where(UserOrgMembership.user_id == bob.id)
                .values(source="manual")
            )
            res = await s.execute(select(LdapGroupMapping))
            for m in res.scalars().all():
                await s.delete(m)
            await s.commit()
        await engine.dispose()

        r2 = await c.post(
            "/v1/auth/login",
            json={"email": "bob@corp.com", "password": "bob-pw"},
        )
        assert r2.status_code == 200, r2.text  # manual membership keeps him in
