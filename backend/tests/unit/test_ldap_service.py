"""LdapAuthService: orchestration, resolution, upsert, circuit breaker.

Uses unittest.mock for the LdapClient (no real network) and a real
AsyncSession against a sqlite-async in-memory DB only for the orchestration
checks that don't touch dialect-specific columns. For User/Membership
upsert we use mocked db.add + db.flush like the audit_and_emit unit test."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from adhkar.auth.ldap_errors import (
    LdapAllProvidersFailed,
    LdapConnectionError,
    LdapInvalidCredentials,
    LdapNoAuthorizedGroup,
    LdapServiceBindError,
)
from adhkar.auth.ldap_service import LdapAuthService


def _provider_cfg(name: str, priority: int = 100):
    cfg = MagicMock()
    cfg.id = uuid4()
    cfg.name = name
    cfg.server_uris = [f"ldaps://{name}:636"]
    cfg.bind_dn = "cn=svc,dc=corp,dc=com"
    cfg.bind_password = "svc-pw"
    cfg.base_dn = "dc=corp,dc=com"
    cfg.user_id_attr = "sAMAccountName"
    cfg.user_email_attr = "mail"
    cfg.user_display_name_attr = "displayName"
    cfg.group_membership_attr = "memberOf"
    cfg.tls_required = True
    cfg.allow_insecure = False
    cfg.timeout_seconds = 5
    cfg.priority = priority
    cfg.render_filter = lambda email: f"(mail={email})"
    return cfg


@pytest.mark.asyncio
async def test_try_bind_iterates_in_priority_order(monkeypatch) -> None:
    svc = LdapAuthService(secret_key="x" * 32, redis=None)
    calls: list[str] = []

    def fake_client(cfg):
        c = MagicMock()

        def search(**kwargs):
            calls.append(cfg.name)
            return []

        c.bind_and_search.side_effect = search
        return c

    monkeypatch.setattr(svc, "_build_client", fake_client)
    monkeypatch.setattr(
        svc,
        "_load_enabled_providers",
        AsyncMock(
            return_value=[
                _provider_cfg("p1", priority=10),
                _provider_cfg("p2", priority=20),
            ]
        ),
    )
    with pytest.raises(LdapInvalidCredentials):
        await svc.try_bind(MagicMock(), email="alice@corp.com", password="pw")
    assert calls == ["p1", "p2"]


@pytest.mark.asyncio
async def test_try_bind_returns_first_success(monkeypatch) -> None:
    svc = LdapAuthService(secret_key="x" * 32, redis=None)

    p1 = _provider_cfg("p1", priority=10)
    p2 = _provider_cfg("p2", priority=20)

    def fake_client(cfg):
        c = MagicMock()
        if cfg.name == "p1":
            c.bind_and_search.return_value = [
                {
                    "dn": "cn=alice,...",
                    "attrs": {
                        "mail": ["alice@corp.com"],
                        "displayName": ["Alice"],
                        "memberOf": ["cn=SOC Analysts,..."],
                    },
                }
            ]
            c.user_bind.return_value = True
        return c

    monkeypatch.setattr(svc, "_build_client", fake_client)
    monkeypatch.setattr(
        svc,
        "_load_enabled_providers",
        AsyncMock(return_value=[p1, p2]),
    )
    org_id, profile_id = uuid4(), uuid4()
    monkeypatch.setattr(
        svc,
        "_resolve_memberships",
        AsyncMock(return_value=[(org_id, profile_id)]),
    )
    result = await svc.try_bind(MagicMock(), email="alice@corp.com", password="pw")
    assert result.provider_id == p1.id
    assert result.resolved_memberships == [(org_id, profile_id)]


@pytest.mark.asyncio
async def test_try_bind_skips_connection_failed_provider(monkeypatch) -> None:
    svc = LdapAuthService(secret_key="x" * 32, redis=None)
    p1 = _provider_cfg("p1", priority=10)
    p2 = _provider_cfg("p2", priority=20)

    def fake_client(cfg):
        c = MagicMock()
        if cfg.name == "p1":
            c.bind_and_search.side_effect = LdapConnectionError("down")
        else:
            c.bind_and_search.return_value = [
                {
                    "dn": "cn=alice,...",
                    "attrs": {
                        "mail": ["alice@corp.com"],
                        "displayName": ["Alice"],
                        "memberOf": ["cn=SOC Analysts,..."],
                    },
                }
            ]
            c.user_bind.return_value = True
        return c

    monkeypatch.setattr(svc, "_build_client", fake_client)
    monkeypatch.setattr(svc, "_load_enabled_providers", AsyncMock(return_value=[p1, p2]))
    monkeypatch.setattr(svc, "_resolve_memberships", AsyncMock(return_value=[(uuid4(), uuid4())]))
    result = await svc.try_bind(MagicMock(), email="alice@corp.com", password="pw")
    assert result is not None


@pytest.mark.asyncio
async def test_try_bind_all_providers_failed_raises(monkeypatch) -> None:
    svc = LdapAuthService(secret_key="x" * 32, redis=None)
    p1 = _provider_cfg("p1", priority=10)

    def fake_client(cfg):
        c = MagicMock()
        c.bind_and_search.side_effect = LdapConnectionError("down")
        return c

    monkeypatch.setattr(svc, "_build_client", fake_client)
    monkeypatch.setattr(svc, "_load_enabled_providers", AsyncMock(return_value=[p1]))
    with pytest.raises(LdapAllProvidersFailed):
        await svc.try_bind(MagicMock(), email="alice@corp.com", password="pw")


@pytest.mark.asyncio
async def test_try_bind_invalid_credentials_does_not_skip_to_next_provider(monkeypatch) -> None:
    """Wrong password is a CRED issue, not a server issue — fail fast."""
    svc = LdapAuthService(secret_key="x" * 32, redis=None)
    p1 = _provider_cfg("p1", priority=10)
    p2 = _provider_cfg("p2", priority=20)
    tried: list[str] = []

    def fake_client(cfg):
        tried.append(cfg.name)
        c = MagicMock()
        c.bind_and_search.return_value = [
            {
                "dn": "cn=alice,...",
                "attrs": {"mail": ["alice@corp.com"], "memberOf": []},
            }
        ]
        c.user_bind.return_value = False
        return c

    monkeypatch.setattr(svc, "_build_client", fake_client)
    monkeypatch.setattr(svc, "_load_enabled_providers", AsyncMock(return_value=[p1, p2]))
    with pytest.raises(LdapInvalidCredentials):
        await svc.try_bind(MagicMock(), email="alice@corp.com", password="pw")
    assert tried == ["p1"]


@pytest.mark.asyncio
async def test_no_authorized_group_when_no_mapping_and_no_manual(monkeypatch) -> None:
    svc = LdapAuthService(secret_key="x" * 32, redis=None)
    p1 = _provider_cfg("p1", priority=10)

    def fake_client(cfg):
        c = MagicMock()
        c.bind_and_search.return_value = [
            {
                "dn": "cn=alice,...",
                "attrs": {
                    "mail": ["alice@corp.com"],
                    "displayName": ["Alice"],
                    "memberOf": ["cn=Marketing,..."],
                },
            }
        ]
        c.user_bind.return_value = True
        return c

    monkeypatch.setattr(svc, "_build_client", fake_client)
    monkeypatch.setattr(svc, "_load_enabled_providers", AsyncMock(return_value=[p1]))
    monkeypatch.setattr(svc, "_resolve_memberships", AsyncMock(return_value=[]))
    monkeypatch.setattr(svc, "_count_manual_memberships", AsyncMock(return_value=0))
    with pytest.raises(LdapNoAuthorizedGroup):
        await svc.try_bind(MagicMock(), email="alice@corp.com", password="pw")


@pytest.mark.asyncio
async def test_no_authorized_group_passes_when_manual_membership_exists(monkeypatch) -> None:
    svc = LdapAuthService(secret_key="x" * 32, redis=None)
    p1 = _provider_cfg("p1", priority=10)

    def fake_client(cfg):
        c = MagicMock()
        c.bind_and_search.return_value = [
            {
                "dn": "cn=alice,...",
                "attrs": {
                    "mail": ["alice@corp.com"],
                    "displayName": ["Alice"],
                    "memberOf": ["cn=Marketing,..."],
                },
            }
        ]
        c.user_bind.return_value = True
        return c

    monkeypatch.setattr(svc, "_build_client", fake_client)
    monkeypatch.setattr(svc, "_load_enabled_providers", AsyncMock(return_value=[p1]))
    monkeypatch.setattr(svc, "_resolve_memberships", AsyncMock(return_value=[]))
    monkeypatch.setattr(svc, "_count_manual_memberships", AsyncMock(return_value=1))
    result = await svc.try_bind(MagicMock(), email="alice@corp.com", password="pw")
    assert result.resolved_memberships == []


@pytest.mark.asyncio
async def test_circuit_breaker_skips_provider_when_open(monkeypatch) -> None:
    redis = MagicMock()
    redis.exists = AsyncMock(side_effect=lambda key: 1 if "p1" in str(key) else 0)
    redis.incr = AsyncMock(return_value=1)
    redis.expire = AsyncMock()
    svc = LdapAuthService(secret_key="x" * 32, redis=redis)
    p1 = _provider_cfg("p1", priority=10)
    p2 = _provider_cfg("p2", priority=20)

    def fake_client(cfg):
        c = MagicMock()
        if cfg.name == "p2":
            c.bind_and_search.return_value = [
                {
                    "dn": "cn=alice,...",
                    "attrs": {
                        "mail": ["alice@corp.com"],
                        "displayName": ["A"],
                        "memberOf": [],
                    },
                }
            ]
            c.user_bind.return_value = True
        return c

    monkeypatch.setattr(svc, "_build_client", fake_client)
    monkeypatch.setattr(svc, "_load_enabled_providers", AsyncMock(return_value=[p1, p2]))
    monkeypatch.setattr(svc, "_resolve_memberships", AsyncMock(return_value=[(uuid4(), uuid4())]))
    result = await svc.try_bind(MagicMock(), email="alice@corp.com", password="pw")
    assert result.provider_id == p2.id


@pytest.mark.asyncio
async def test_circuit_breaker_opens_after_threshold(monkeypatch) -> None:
    redis = MagicMock()
    open_set = False

    async def fake_set(key, value, ex=None):
        nonlocal open_set
        if "open" in str(key):
            open_set = True

    redis.exists = AsyncMock(return_value=0)
    redis.incr = AsyncMock(return_value=51)
    redis.expire = AsyncMock()
    redis.set = AsyncMock(side_effect=fake_set)
    svc = LdapAuthService(secret_key="x" * 32, redis=redis)
    p1 = _provider_cfg("p1", priority=10)

    def fake_client(cfg):
        c = MagicMock()
        c.bind_and_search.side_effect = LdapConnectionError("down")
        return c

    monkeypatch.setattr(svc, "_build_client", fake_client)
    monkeypatch.setattr(svc, "_load_enabled_providers", AsyncMock(return_value=[p1]))
    with pytest.raises(LdapAllProvidersFailed):
        await svc.try_bind(MagicMock(), email="a@corp.com", password="pw")
    assert open_set is True


@pytest.mark.asyncio
async def test_service_bind_error_audited_but_continues(monkeypatch) -> None:
    svc = LdapAuthService(secret_key="x" * 32, redis=None)
    p1 = _provider_cfg("p1", priority=10)
    p2 = _provider_cfg("p2", priority=20)

    def fake_client(cfg):
        c = MagicMock()
        if cfg.name == "p1":
            c.bind_and_search.side_effect = LdapServiceBindError("wrong svc pw")
        else:
            c.bind_and_search.return_value = [
                {
                    "dn": "cn=alice,...",
                    "attrs": {
                        "mail": ["alice@corp.com"],
                        "displayName": ["A"],
                        "memberOf": ["cn=SOC,..."],
                    },
                }
            ]
            c.user_bind.return_value = True
        return c

    monkeypatch.setattr(svc, "_build_client", fake_client)
    monkeypatch.setattr(svc, "_load_enabled_providers", AsyncMock(return_value=[p1, p2]))
    monkeypatch.setattr(svc, "_resolve_memberships", AsyncMock(return_value=[(uuid4(), uuid4())]))
    result = await svc.try_bind(MagicMock(), email="a@corp.com", password="pw")
    assert result.provider_id == p2.id
