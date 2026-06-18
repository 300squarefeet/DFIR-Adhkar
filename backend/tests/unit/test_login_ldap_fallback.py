"""POST /v1/auth/login transparent fallback to LDAP.

We test the handler's branching logic by calling the login() coroutine
directly with mocked DB sessions and a patched _ldap_service_factory.
No real DB, no real Redis, no real LDAP server.

Scenarios:
  1. Local password success — LDAP NOT called.
  2. Local password mismatch (anti-pivot) — LDAP NOT called, 401.
  3. Unknown email, no LdapProvider row → 401 (providers is None early-out).
  4. Unknown email, provider row seeded, LDAP succeeds → 200 + access_token.
  5. LdapInvalidCredentials → 401 invalid_credentials.
  6. LdapNoAuthorizedGroup → 403 ldap_no_authorized_group.
  7. LdapAllProvidersFailed → 503 ldap_unavailable.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from adhkar.auth.ldap_errors import (
    LdapAllProvidersFailed,
    LdapInvalidCredentials,
    LdapNoAuthorizedGroup,
)
from adhkar.auth.ldap_service import BindResult
from adhkar.auth.password import hash_password
from fastapi import HTTPException, Request, Response
from starlette import status as http_status

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_settings() -> Any:
    s = MagicMock()
    s.secret_key = "x" * 32
    s.env = "test"
    return s


def _make_request() -> Request:
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/v1/auth/login",
        "query_string": b"",
        "headers": [],
    }
    return Request(scope)


def _make_response() -> Response:
    return Response()


def _make_login_body(email: str = "user@example.com", password: str = "pw") -> Any:
    body = MagicMock()
    body.email = email
    body.password = password
    return body


def _scalar_result(value: Any) -> Any:
    """Return an async-compatible execute() mock that yields scalar_one_or_none=value."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    result.scalar_one.return_value = value
    return result


def _scalars_result(items: list[Any]) -> Any:
    """Return a result whose .scalars().all() = items and .scalars().first() = items[0] or None."""
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = items
    scalars_mock.first.return_value = items[0] if items else None
    result = MagicMock()
    result.scalars.return_value = scalars_mock
    return result


def _make_user(
    *,
    email: str = "user@example.com",
    password_hash: str | None = None,
    status: str = "active",
    default_org_id: Any = None,
) -> Any:
    u = MagicMock()
    u.id = uuid4()
    u.email = email
    u.password_hash = password_hash
    u.status = status
    u.default_org_id = default_org_id
    return u


def _make_membership(user_id: Any, org_id: Any, profile_id: Any) -> Any:
    m = MagicMock()
    m.user_id = user_id
    m.organization_id = org_id
    m.profile_id = profile_id
    return m


def _make_profile(permissions: list[str] | None = None) -> Any:
    p = MagicMock()
    p.id = uuid4()
    p.permissions = permissions or ["viewCase"]
    return p


def _build_db_for_local_success(user: Any, membership: Any, profile: Any) -> AsyncMock:
    """Build a mock AsyncSession for a successful local-password login.

    execute() is called 3 times:
      1. SELECT user by email  -> user
      2. SELECT memberships    -> [membership]
      3. SELECT profile        -> profile
    """
    db = MagicMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.delete = AsyncMock()

    execute_calls: list[Any] = []

    async def fake_execute(stmt: Any) -> Any:
        count = len(execute_calls)
        execute_calls.append(stmt)
        if count == 0:
            # SELECT User
            return _scalar_result(user)
        elif count == 1:
            # SELECT UserOrgMembership
            return _scalars_result([membership])
        else:
            # SELECT Profile
            return _scalar_result(profile)

    db.execute = fake_execute
    return db


# ---------------------------------------------------------------------------
# Test 1: local password success — LDAP NOT called
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_local_password_success_does_not_call_ldap() -> None:
    """Existing user with correct password_hash -> 200, LDAP try_bind never called."""
    from adhkar.api.v1 import auth as auth_module
    from adhkar.api.v1.auth import login

    org_id = uuid4()
    profile_id = uuid4()
    pw = "correct-password"
    user = _make_user(password_hash=hash_password(pw), default_org_id=org_id)
    membership = _make_membership(user.id, org_id, profile_id)
    profile = _make_profile(["viewCase"])
    membership.organization_id = org_id
    membership.profile_id = profile_id

    db = _build_db_for_local_success(user, membership, profile)

    fake_svc = MagicMock()
    fake_svc.try_bind = AsyncMock(side_effect=AssertionError("LDAP must not be called"))

    with patch.object(auth_module, "_ldap_service_factory", return_value=fake_svc):
        resp = await login(
            body=_make_login_body(password=pw),
            request=_make_request(),
            response=_make_response(),
            settings=_make_settings(),
            db=db,
            redis=None,
        )

    assert resp.access_token  # non-empty JWT string
    fake_svc.try_bind.assert_not_called()


# ---------------------------------------------------------------------------
# Test 2: local password MISMATCH (anti-pivot) — LDAP NOT called
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_local_password_mismatch_does_not_call_ldap() -> None:
    """User with password_hash + wrong password -> 401 immediately, NO LDAP."""
    from adhkar.api.v1 import auth as auth_module
    from adhkar.api.v1.auth import login

    user = _make_user(password_hash=hash_password("correct-password"))

    db = MagicMock()

    async def fake_execute(stmt: Any) -> Any:
        return _scalar_result(user)

    db.execute = fake_execute

    fake_svc = MagicMock()
    fake_svc.try_bind = AsyncMock(side_effect=AssertionError("LDAP must not be called"))

    with patch.object(auth_module, "_ldap_service_factory", return_value=fake_svc):
        with pytest.raises(HTTPException) as exc_info:
            await login(
                body=_make_login_body(password="wrong-password"),
                request=_make_request(),
                response=_make_response(),
                settings=_make_settings(),
                db=db,
                redis=None,
            )

    assert exc_info.value.status_code == http_status.HTTP_401_UNAUTHORIZED
    assert exc_info.value.detail == "invalid_credentials"
    fake_svc.try_bind.assert_not_called()


# ---------------------------------------------------------------------------
# Test 3a: unknown email, NO provider row -> 401
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unknown_email_no_provider_returns_401() -> None:
    """No User row, no LdapProvider row -> 401 invalid_credentials (provider early-out)."""
    from adhkar.api.v1.auth import login

    db = MagicMock()
    call_count = 0

    async def fake_execute(stmt: Any) -> Any:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # SELECT User -> None
            return _scalar_result(None)
        else:
            # SELECT LdapProvider -> empty
            return _scalars_result([])

    db.execute = fake_execute

    with pytest.raises(HTTPException) as exc_info:
        await login(
            body=_make_login_body(email="nobody@example.com"),
            request=_make_request(),
            response=_make_response(),
            settings=_make_settings(),
            db=db,
            redis=None,
        )

    assert exc_info.value.status_code == http_status.HTTP_401_UNAUTHORIZED
    assert exc_info.value.detail == "invalid_credentials"


# ---------------------------------------------------------------------------
# Test 3b: unknown email, provider EXISTS, LDAP succeeds -> 200 + access_token
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unknown_email_with_provider_and_ldap_success_returns_200() -> None:
    """No User row, but LdapProvider exists + try_bind succeeds -> 200."""
    from adhkar.api.v1 import auth as auth_module
    from adhkar.api.v1.auth import login

    org_id = uuid4()
    profile_id = uuid4()

    # The user that upsert_user_and_memberships will return
    upserted_user = _make_user(email="ldap-user@corp.com", status="active", default_org_id=org_id)
    membership = _make_membership(upserted_user.id, org_id, profile_id)
    membership.organization_id = org_id
    membership.profile_id = profile_id
    profile = _make_profile(["viewCase"])

    bind_result = BindResult(
        provider_id=uuid4(),
        user_dn="cn=ldap-user,dc=corp,dc=com",
        email="ldap-user@corp.com",
        display_name="LDAP User",
        matched_group_dns=["cn=SOC,..."],
        resolved_memberships=[(org_id, profile_id)],
    )

    fake_provider = MagicMock()  # just needs to be non-None

    db = MagicMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.delete = AsyncMock()
    execute_call_count = 0

    async def fake_execute(stmt: Any) -> Any:
        nonlocal execute_call_count
        execute_call_count += 1
        if execute_call_count == 1:
            # SELECT User -> None (unknown)
            return _scalar_result(None)
        elif execute_call_count == 2:
            # SELECT LdapProvider -> [fake_provider]
            return _scalars_result([fake_provider])
        elif execute_call_count == 3:
            # SELECT UserOrgMembership (after upsert)
            return _scalars_result([membership])
        else:
            # SELECT Profile
            return _scalar_result(profile)

    db.execute = fake_execute

    fake_svc = MagicMock()
    fake_svc.try_bind = AsyncMock(return_value=bind_result)
    fake_svc.upsert_user_and_memberships = AsyncMock(return_value=upserted_user)

    with patch.object(auth_module, "_ldap_service_factory", return_value=fake_svc):
        resp = await login(
            body=_make_login_body(email="ldap-user@corp.com", password="ldap-pw"),
            request=_make_request(),
            response=_make_response(),
            settings=_make_settings(),
            db=db,
            redis=None,
        )

    assert resp.access_token
    assert str(resp.user_id) == str(upserted_user.id)
    fake_svc.try_bind.assert_awaited_once()
    fake_svc.upsert_user_and_memberships.assert_awaited_once()


# ---------------------------------------------------------------------------
# Test 4: LdapInvalidCredentials -> 401
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ldap_invalid_credentials_maps_to_401() -> None:
    """try_bind raises LdapInvalidCredentials -> 401 invalid_credentials."""
    from adhkar.api.v1 import auth as auth_module
    from adhkar.api.v1.auth import login

    fake_provider = MagicMock()

    db = MagicMock()
    call_count = 0

    async def fake_execute(stmt: Any) -> Any:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _scalar_result(None)
        return _scalars_result([fake_provider])

    db.execute = fake_execute

    fake_svc = MagicMock()
    fake_svc.try_bind = AsyncMock(side_effect=LdapInvalidCredentials("bad creds"))

    with patch.object(auth_module, "_ldap_service_factory", return_value=fake_svc):
        with pytest.raises(HTTPException) as exc_info:
            await login(
                body=_make_login_body(email="user@corp.com"),
                request=_make_request(),
                response=_make_response(),
                settings=_make_settings(),
                db=db,
                redis=None,
            )

    assert exc_info.value.status_code == http_status.HTTP_401_UNAUTHORIZED
    assert exc_info.value.detail == "invalid_credentials"


# ---------------------------------------------------------------------------
# Test 5: LdapNoAuthorizedGroup -> 403
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ldap_no_authorized_group_maps_to_403() -> None:
    """try_bind raises LdapNoAuthorizedGroup -> 403 ldap_no_authorized_group."""
    from adhkar.api.v1 import auth as auth_module
    from adhkar.api.v1.auth import login

    fake_provider = MagicMock()

    db = MagicMock()
    call_count = 0

    async def fake_execute(stmt: Any) -> Any:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _scalar_result(None)
        return _scalars_result([fake_provider])

    db.execute = fake_execute

    fake_svc = MagicMock()
    fake_svc.try_bind = AsyncMock(side_effect=LdapNoAuthorizedGroup("not in any group"))

    with patch.object(auth_module, "_ldap_service_factory", return_value=fake_svc):
        with pytest.raises(HTTPException) as exc_info:
            await login(
                body=_make_login_body(email="user@corp.com"),
                request=_make_request(),
                response=_make_response(),
                settings=_make_settings(),
                db=db,
                redis=None,
            )

    assert exc_info.value.status_code == http_status.HTTP_403_FORBIDDEN
    assert exc_info.value.detail == "ldap_no_authorized_group"


# ---------------------------------------------------------------------------
# Test 6: LdapAllProvidersFailed -> 503
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ldap_all_providers_failed_maps_to_503() -> None:
    """try_bind raises LdapAllProvidersFailed -> 503 ldap_unavailable."""
    from adhkar.api.v1 import auth as auth_module
    from adhkar.api.v1.auth import login

    fake_provider = MagicMock()

    db = MagicMock()
    call_count = 0

    async def fake_execute(stmt: Any) -> Any:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _scalar_result(None)
        return _scalars_result([fake_provider])

    db.execute = fake_execute

    fake_svc = MagicMock()
    fake_svc.try_bind = AsyncMock(side_effect=LdapAllProvidersFailed("all down"))

    with patch.object(auth_module, "_ldap_service_factory", return_value=fake_svc):
        with pytest.raises(HTTPException) as exc_info:
            await login(
                body=_make_login_body(email="user@corp.com"),
                request=_make_request(),
                response=_make_response(),
                settings=_make_settings(),
                db=db,
                redis=None,
            )

    assert exc_info.value.status_code == http_status.HTTP_503_SERVICE_UNAVAILABLE
    assert exc_info.value.detail == "ldap_unavailable"


# ---------------------------------------------------------------------------
# Bonus: BindResult dataclass integrity
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bind_result_shape() -> None:
    """BindResult dataclass carries expected fields."""
    result = BindResult(
        provider_id=uuid4(),
        user_dn="cn=alice,dc=corp,dc=com",
        email="alice@corp.com",
        display_name="Alice",
        matched_group_dns=["cn=SOC,..."],
        resolved_memberships=[(uuid4(), uuid4())],
    )
    assert result.email == "alice@corp.com"
    assert len(result.resolved_memberships) == 1
