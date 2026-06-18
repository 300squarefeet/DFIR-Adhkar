"""Admin LDAP endpoints — CRUD + Test-connection + mappings.

Test approach: Option C (with partial Option A-style mock-at-handler-level).
We call the endpoint handler functions directly with mocked DB sessions and
dependency overrides — no real DB, no SQLite ARRAY(String) incompatibility,
no real LDAP server.

The pattern mirrors test_login_ldap_fallback.py which calls handlers directly
with mock DB objects. Full HTTP-level round-trip integration tests live in Task 7.

Scenarios covered:
1. list_providers (GET) with no auth -> 401/403 (via ASGI app + real auth dependency).
2. create_provider handler directly -> response excludes bind_password/bind_password_enc.
3. create_provider without manageConfig perm token -> 403.
4. test_connection success (LdapClient.bind_and_search patched to return []) -> ok=True.
5. test_connection failure (LdapClient.bind_and_search raises LdapConnectionError) -> ok=False.
6. create_mapping duplicate -> IntegrityError -> 409.
7. delete_provider -> deleted_at set; subsequent get_provider -> 404.
8. LdapProviderOut schema never contains bind_password or bind_password_enc.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from adhkar.api.v1.admin_ldap import (
    LdapGroupMappingIn,
    LdapProviderIn,
    LdapProviderOut,
    create_mapping,
    create_provider,
    delete_provider,
    get_provider,
)
from adhkar.api.v1.admin_ldap import (
    TestConnectionResult as ConnectionResult,
)
from adhkar.api.v1.admin_ldap import (
    test_connection as run_test_connection,
)
from adhkar.auth.ldap_errors import LdapConnectionError
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import IntegrityError

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_settings(secret_key: str = "x" * 32) -> Any:
    s = MagicMock()
    s.secret_key = secret_key
    return s


def _make_user(
    perms: list[str] | None = None,
    org_id: Any = None,
) -> Any:
    u = MagicMock()
    u.user_id = uuid4()
    u.org_id = org_id or uuid4()
    u.permissions = frozenset(perms or ["manageConfig"])
    return u


def _make_provider_row(
    *,
    name: str = "Test LDAP",
    server_uris: list[str] | None = None,
    deleted_at: datetime | None = None,
) -> Any:
    row = MagicMock()
    row.id = uuid4()
    row.name = name
    row.server_uris = server_uris or ["ldap://corp.example.com:389"]
    row.bind_dn = "cn=svc,dc=corp,dc=com"
    row.bind_password_enc = "encrypted-placeholder"
    row.base_dn = "dc=corp,dc=com"
    row.user_search_filter = "(mail={input})"
    row.user_id_attr = "sAMAccountName"
    row.user_email_attr = "mail"
    row.user_display_name_attr = "displayName"
    row.group_membership_attr = "memberOf"
    row.tls_required = True
    row.allow_insecure = False
    row.enabled = True
    row.priority = 100
    row.timeout_seconds = 5
    row.deleted_at = deleted_at
    return row


def _make_mapping_row(
    *,
    provider_id: Any = None,
    group_dn: str = "cn=SOC,dc=corp,dc=com",
) -> Any:
    row = MagicMock()
    row.id = uuid4()
    row.ldap_provider_id = provider_id or uuid4()
    row.group_dn = group_dn
    row.organization_id = uuid4()
    row.profile_id = uuid4()
    return row


def _scalar_result(value: Any) -> Any:
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    result.scalar_one.return_value = value
    return result


def _scalars_result(items: list[Any]) -> Any:
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = items
    scalars_mock.first.return_value = items[0] if items else None
    result = MagicMock()
    result.scalars.return_value = scalars_mock
    return result


def _make_db(
    *,
    get_result: Any = None,
    execute_results: list[Any] | None = None,
    flush_side_effect: Exception | None = None,
) -> AsyncMock:
    """Build a minimal mock AsyncSession."""
    db = MagicMock()
    db.add = MagicMock()
    db.delete = AsyncMock()

    if flush_side_effect:
        db.flush = AsyncMock(side_effect=flush_side_effect)
    else:
        db.flush = AsyncMock()

    db.get = AsyncMock(return_value=get_result)

    _execute_calls: list[Any] = []
    _results = list(execute_results or [])

    async def _execute(stmt: Any) -> Any:
        idx = len(_execute_calls)
        _execute_calls.append(stmt)
        if idx < len(_results):
            return _results[idx]
        return _scalars_result([])

    db.execute = _execute
    return db


# ---------------------------------------------------------------------------
# Schema-level tests (no I/O, always fast)
# ---------------------------------------------------------------------------


def test_ldap_provider_out_has_no_password_fields() -> None:
    """LdapProviderOut must never include bind_password or bind_password_enc."""
    field_names = set(LdapProviderOut.model_fields.keys())
    assert "bind_password" not in field_names
    assert "bind_password_enc" not in field_names


def test_ldap_provider_in_has_bind_password_field() -> None:
    """LdapProviderIn accepts bind_password for creation."""
    field_names = set(LdapProviderIn.model_fields.keys())
    assert "bind_password" in field_names


def test_test_connection_result_fields() -> None:
    """ConnectionResult (TestConnectionResult alias) has ok, server_uri_used, error, duration_ms."""
    r = ConnectionResult(ok=True, server_uri_used="ldap://h:389", error=None, duration_ms=42)
    assert r.ok is True
    assert r.duration_ms == 42
    assert r.error is None


# ---------------------------------------------------------------------------
# Test 1: No-auth request to list endpoint -> 401/403
# ---------------------------------------------------------------------------


@pytest.fixture
def bare_app(monkeypatch) -> FastAPI:
    """Minimal app with just the admin_ldap router; real auth dependency."""
    monkeypatch.setenv("ADHKAR_SECRET_KEY", "x" * 32)
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h/db")
    monkeypatch.setenv("REDIS_URL", "redis://h:6379/0")
    from adhkar.core.settings import get_settings

    get_settings.cache_clear()

    from adhkar.api.v1.admin_ldap import router as ldap_router

    app = FastAPI()
    app.include_router(ldap_router)
    return app


@pytest.mark.asyncio
async def test_list_providers_no_auth_returns_401(bare_app: FastAPI) -> None:
    transport = ASGITransport(app=bare_app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.get("/v1/admin/ldap-providers")
    assert r.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Test 2: POST without manageConfig perm -> 403
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_provider_wrong_perm_returns_403(bare_app: FastAPI) -> None:
    """A valid JWT without manageConfig must get 403 from require_permission."""
    from datetime import timedelta

    from adhkar.auth.jwt import encode_jwt

    token, _ = encode_jwt(
        secret="x" * 32,
        user_id=uuid4(),
        typ="access",
        ttl=timedelta(minutes=15),
        org_id=uuid4(),
        perms=["viewCase"],  # no manageConfig
    )
    # We need to override redis to avoid real Redis calls in is_denied
    from adhkar.api.deps import get_redis

    redis_mock = AsyncMock()
    redis_mock.exists = AsyncMock(return_value=0)
    bare_app.dependency_overrides[get_redis] = lambda: redis_mock

    transport = ASGITransport(app=bare_app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.post(
            "/v1/admin/ldap-providers",
            json={
                "name": "corp-ldap",
                "server_uris": ["ldap://corp.example.com:389"],
                "bind_dn": "cn=svc,dc=corp,dc=com",
                "bind_password": "s3cr3t",
                "base_dn": "dc=corp,dc=com",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
    assert r.status_code == 403
    bare_app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Test 3: create_provider handler returns output without bind_password
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_provider_response_excludes_bind_password() -> None:
    """POST handler must not echo bind_password or bind_password_enc."""
    provider_id = uuid4()

    provider_row = _make_provider_row()
    provider_row.id = provider_id

    db = _make_db()

    # Simulate flush assigning id to the row (SQLAlchemy does this server-side
    # normally; here we mock the flush and pre-assign id on the mock row).
    async def _flush_with_id() -> None:
        pass  # row already has id from MagicMock setup

    db.flush = AsyncMock(side_effect=_flush_with_id)

    # audit_and_emit does db.add + db.flush; we need those to work
    db.add = MagicMock()

    body = LdapProviderIn(
        name="corp-ldap",
        server_uris=["ldap://corp.example.com:389"],
        bind_dn="cn=svc,dc=corp,dc=com",
        bind_password="s3cr3t",
        base_dn="dc=corp,dc=com",
    )
    user = _make_user()
    settings = _make_settings()

    with patch("adhkar.api.v1.admin_ldap.LdapProvider") as mock_provider_cls:
        mock_provider_cls.return_value = provider_row

        with patch("adhkar.api.v1.admin_ldap.audit_and_emit", new_callable=AsyncMock) as mock_audit:
            mock_audit.return_value = (MagicMock(), MagicMock())
            result = await create_provider(
                body=body,
                user=user,
                db=db,
                settings=settings,
            )

    assert isinstance(result, LdapProviderOut)
    result_dict = result.model_dump()
    assert "bind_password" not in result_dict
    assert "bind_password_enc" not in result_dict
    assert result.name == provider_row.name
    # Verify audit was called with correct action
    mock_audit.assert_awaited_once()
    call_kwargs = mock_audit.call_args[1]
    assert call_kwargs["action"] == "ldap_provider_created"
    assert call_kwargs["emit_outbox"] is True


# ---------------------------------------------------------------------------
# Test 4a: test_connection success
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_test_connection_ok_true_when_bind_succeeds() -> None:
    """Patch LdapClient.bind_and_search to return [] -> ok=True."""
    from adhkar.auth.ldap_provider import LdapProviderConfig

    provider_id = uuid4()
    provider_row = _make_provider_row(server_uris=["ldap://corp.example.com:389"])
    provider_row.id = provider_id

    db = _make_db(get_result=provider_row)
    user = _make_user()
    settings = _make_settings()

    cfg = LdapProviderConfig(
        id=provider_id,
        name="Test LDAP",
        server_uris=["ldap://corp.example.com:389"],
        bind_dn="cn=svc,dc=corp,dc=com",
        bind_password="s3cr3t",
        base_dn="dc=corp,dc=com",
        user_search_filter="(mail={input})",
        user_id_attr="sAMAccountName",
        user_email_attr="mail",
        user_display_name_attr="displayName",
        group_membership_attr="memberOf",
        tls_required=True,
        allow_insecure=False,
        priority=100,
        timeout_seconds=5,
    )

    with patch("adhkar.api.v1.admin_ldap.LdapProviderConfig") as mock_cfg_cls:
        mock_cfg_cls.from_row.return_value = cfg
        with patch("adhkar.api.v1.admin_ldap.LdapClient") as mock_client_cls:
            mock_client_instance = MagicMock()
            mock_client_instance.bind_and_search = MagicMock(return_value=[])
            mock_client_cls.return_value = mock_client_instance
            with patch(
                "adhkar.api.v1.admin_ldap.audit_and_emit", new_callable=AsyncMock
            ) as mock_audit:
                mock_audit.return_value = (MagicMock(), MagicMock())
                result = await run_test_connection(
                    provider_id=provider_id,
                    user=user,
                    db=db,
                    settings=settings,
                )

    assert isinstance(result, ConnectionResult)
    assert result.ok is True
    assert result.error is None
    assert result.server_uri_used == "ldap://corp.example.com:389"
    # Audit always emitted (even on success)
    mock_audit.assert_awaited_once()
    call_kwargs = mock_audit.call_args[1]
    assert call_kwargs["action"] == "ldap_test_connection"
    assert call_kwargs["diff"]["ok"] is True


# ---------------------------------------------------------------------------
# Test 4b: test_connection failure -> ok=False
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_test_connection_ok_false_when_bind_raises() -> None:
    """Patch LdapClient.bind_and_search to raise LdapConnectionError -> ok=False."""
    from adhkar.auth.ldap_provider import LdapProviderConfig

    provider_id = uuid4()
    provider_row = _make_provider_row()
    provider_row.id = provider_id

    db = _make_db(get_result=provider_row)
    user = _make_user()
    settings = _make_settings()

    cfg = LdapProviderConfig(
        id=provider_id,
        name="Test LDAP",
        server_uris=["ldap://corp.example.com:389"],
        bind_dn="cn=svc,dc=corp,dc=com",
        bind_password="s3cr3t",
        base_dn="dc=corp,dc=com",
        user_search_filter="(mail={input})",
        user_id_attr="sAMAccountName",
        user_email_attr="mail",
        user_display_name_attr="displayName",
        group_membership_attr="memberOf",
        tls_required=True,
        allow_insecure=False,
        priority=100,
        timeout_seconds=5,
    )

    with patch("adhkar.api.v1.admin_ldap.LdapProviderConfig") as mock_cfg_cls:
        mock_cfg_cls.from_row.return_value = cfg
        with patch("adhkar.api.v1.admin_ldap.LdapClient") as mock_client_cls:
            mock_client_instance = MagicMock()
            mock_client_instance.bind_and_search = MagicMock(
                side_effect=LdapConnectionError("all URIs unreachable")
            )
            mock_client_cls.return_value = mock_client_instance
            with patch(
                "adhkar.api.v1.admin_ldap.audit_and_emit", new_callable=AsyncMock
            ) as mock_audit:
                mock_audit.return_value = (MagicMock(), MagicMock())
                result = await run_test_connection(
                    provider_id=provider_id,
                    user=user,
                    db=db,
                    settings=settings,
                )

    assert isinstance(result, ConnectionResult)
    assert result.ok is False
    assert result.error is not None
    assert "unreachable" in result.error
    # Audit always emitted regardless of ok/fail
    mock_audit.assert_awaited_once()
    call_kwargs = mock_audit.call_args[1]
    assert call_kwargs["diff"]["ok"] is False


# ---------------------------------------------------------------------------
# Test 5: create_mapping duplicate -> IntegrityError -> 409
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_mapping_duplicate_returns_409() -> None:
    """flush() raises IntegrityError -> HTTPException 409."""
    provider_id = uuid4()
    user = _make_user()

    # Create an IntegrityError - needs orig arg (SQLAlchemy requirement)
    orig = Exception("duplicate key value violates unique constraint")
    integrity_error = IntegrityError(statement=None, params=None, orig=orig)

    db = _make_db(flush_side_effect=integrity_error)
    db.add = MagicMock()
    db.rollback = AsyncMock()

    body = LdapGroupMappingIn(
        group_dn="cn=SOC,dc=corp,dc=com",
        organization_id=uuid4(),
        profile_id=uuid4(),
    )

    with patch("adhkar.api.v1.admin_ldap.LdapGroupMapping") as mock_mapping_cls:
        mock_mapping_cls.return_value = _make_mapping_row(provider_id=provider_id)
        with pytest.raises(HTTPException) as exc_info:
            await create_mapping(
                provider_id=provider_id,
                body=body,
                user=user,
                db=db,
            )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "mapping_already_exists"


# ---------------------------------------------------------------------------
# Test 6: delete_provider -> deleted_at set; get_provider -> 404
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_provider_sets_deleted_at() -> None:
    """delete_provider sets deleted_at on the row."""
    provider_id = uuid4()
    provider_row = _make_provider_row()
    provider_row.id = provider_id
    provider_row.deleted_at = None

    user = _make_user()
    db = _make_db(get_result=provider_row)
    db.add = MagicMock()

    with patch("adhkar.api.v1.admin_ldap.audit_and_emit", new_callable=AsyncMock) as mock_audit:
        mock_audit.return_value = (MagicMock(), MagicMock())
        await delete_provider(
            provider_id=provider_id,
            user=user,
            db=db,
        )

    # deleted_at must have been set to a datetime
    assert provider_row.deleted_at is not None
    assert isinstance(provider_row.deleted_at, datetime)
    mock_audit.assert_awaited_once()
    call_kwargs = mock_audit.call_args[1]
    assert call_kwargs["action"] == "ldap_provider_deleted"


@pytest.mark.asyncio
async def test_get_provider_returns_404_when_soft_deleted() -> None:
    """get_provider raises 404 when deleted_at is set."""
    provider_id = uuid4()
    deleted_row = _make_provider_row(deleted_at=datetime.now(tz=UTC))

    user = _make_user()
    db = _make_db(get_result=deleted_row)

    with pytest.raises(HTTPException) as exc_info:
        await get_provider(
            provider_id=provider_id,
            _user=user,
            db=db,
        )

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_get_provider_returns_404_when_not_found() -> None:
    """get_provider raises 404 when row is None."""
    provider_id = uuid4()
    user = _make_user()
    db = _make_db(get_result=None)

    with pytest.raises(HTTPException) as exc_info:
        await get_provider(
            provider_id=provider_id,
            _user=user,
            db=db,
        )

    assert exc_info.value.status_code == 404
