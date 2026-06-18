"""Typed exception hierarchy for LDAP auth."""

from __future__ import annotations

from adhkar.auth.ldap_errors import (
    LdapAllProvidersFailed,
    LdapConnectionError,
    LdapError,
    LdapInvalidCredentials,
    LdapNoAuthorizedGroup,
    LdapServiceBindError,
    LdapUserNotFound,
    status_code_for,
)
from fastapi import status


def test_invalid_credentials_maps_to_401() -> None:
    assert status_code_for(LdapInvalidCredentials("x")) == status.HTTP_401_UNAUTHORIZED


def test_user_not_found_maps_to_401() -> None:
    # anti-enumeration: identical status to wrong-password
    assert status_code_for(LdapUserNotFound("x")) == status.HTTP_401_UNAUTHORIZED


def test_no_authorized_group_maps_to_403() -> None:
    assert status_code_for(LdapNoAuthorizedGroup("x")) == status.HTTP_403_FORBIDDEN


def test_all_providers_failed_maps_to_503() -> None:
    assert status_code_for(LdapAllProvidersFailed("x")) == status.HTTP_503_SERVICE_UNAVAILABLE


def test_subclassing_preserved() -> None:
    assert issubclass(LdapConnectionError, LdapError)
    assert issubclass(LdapServiceBindError, LdapError)
    assert issubclass(LdapInvalidCredentials, LdapError)


def test_password_not_leaked_in_exception_repr() -> None:
    secret = "hunter2-super-secret"
    err = LdapInvalidCredentials("user_dn=cn=alice,...; reason=invalidCredentials")
    # Implementer MUST NOT pass password into the exception. This is a regression guard.
    assert secret not in repr(err)
    assert secret not in str(err)
