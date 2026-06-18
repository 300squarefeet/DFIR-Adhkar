"""Frozen LdapProviderConfig built from an LdapProvider row.

Decrypts the bind password via adhkar.auth.crypto. Validates server URI
shape. Has zero database knowledge — pure transformation."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse
from uuid import UUID

from adhkar.auth.crypto import decrypt
from adhkar.db.models import LdapProvider

_URI_SCHEMES = {"ldap", "ldaps"}

_ESCAPE_MAP = {"\\": r"\5c", "*": r"\2a", "(": r"\28", ")": r"\29", "\x00": r"\00"}


def validate_server_uris(uris: list[str]) -> None:
    for raw in uris:
        try:
            parsed = urlparse(raw)
        except ValueError as exc:
            raise ValueError(f"invalid server URI: {raw}") from exc
        if parsed.scheme not in _URI_SCHEMES or not parsed.hostname:
            raise ValueError(f"invalid server URI: {raw}")


@dataclass(frozen=True, slots=True)
class LdapProviderConfig:
    id: UUID
    name: str
    server_uris: list[str]
    bind_dn: str
    bind_password: str  # plain — never log
    base_dn: str
    user_search_filter: str
    user_id_attr: str
    user_email_attr: str
    user_display_name_attr: str
    group_membership_attr: str
    tls_required: bool
    allow_insecure: bool
    priority: int
    timeout_seconds: int

    @classmethod
    def from_row(cls, row: LdapProvider, secret_key: str) -> LdapProviderConfig:
        validate_server_uris(list(row.server_uris))
        plain = decrypt(row.bind_password_enc.encode(), secret_key).decode()
        return cls(
            id=row.id,
            name=row.name,
            server_uris=list(row.server_uris),
            bind_dn=row.bind_dn,
            bind_password=plain,
            base_dn=row.base_dn,
            user_search_filter=row.user_search_filter,
            user_id_attr=row.user_id_attr,
            user_email_attr=row.user_email_attr,
            user_display_name_attr=row.user_display_name_attr,
            group_membership_attr=row.group_membership_attr,
            tls_required=row.tls_required,
            allow_insecure=row.allow_insecure,
            priority=row.priority,
            timeout_seconds=row.timeout_seconds,
        )

    def render_filter(self, input_value: str) -> str:
        """Substitute {input} placeholder with the LDAP-escaped value (RFC 4515)."""
        escaped = "".join(_ESCAPE_MAP.get(c, c) for c in input_value)
        return self.user_search_filter.replace("{input}", escaped)
