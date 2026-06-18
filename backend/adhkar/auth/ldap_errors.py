"""Typed exception hierarchy for LDAP authentication.

Mirror the SAML errors pattern. Endpoint mappers translate these to RFC 7807
problem details. Implementers MUST NOT include user passwords in exception
args or messages."""

from __future__ import annotations

from fastapi import status


class LdapError(Exception):
    """Base for all LDAP-related auth failures."""


class LdapConnectionError(LdapError):
    """Socket/TLS failure. Caller treats as 'try next provider'."""


class LdapServiceBindError(LdapError):
    """Service-account credentials wrong/expired. Operator misconfig."""


class LdapInvalidCredentials(LdapError):  # noqa: N818
    """User-supplied password wrong, OR empty-password reject."""


class LdapUserNotFound(LdapError):  # noqa: N818
    """Search returned 0 entries. Anti-enumeration: maps to same 401."""


class LdapNoAuthorizedGroup(LdapError):  # noqa: N818
    """Bind ok but no group mapping matched and no manual membership exists."""


class LdapAllProvidersFailed(LdapError):  # noqa: N818
    """Every enabled provider raised LdapConnectionError / LdapServiceBindError."""


def status_code_for(err: LdapError) -> int:
    if isinstance(err, LdapNoAuthorizedGroup):
        return status.HTTP_403_FORBIDDEN
    if isinstance(err, LdapAllProvidersFailed):
        return status.HTTP_503_SERVICE_UNAVAILABLE
    return status.HTTP_401_UNAUTHORIZED
