"""LdapProviderConfig: Fernet round-trip + URI validation."""

from __future__ import annotations

import pytest
from adhkar.auth.crypto import encrypt
from adhkar.auth.ldap_provider import LdapProviderConfig, validate_server_uris
from adhkar.db.models import LdapProvider

SECRET = "x" * 32


def _row(uris: list[str], encrypted_pw: bytes) -> LdapProvider:
    return LdapProvider(
        name="corp",
        server_uris=uris,
        bind_dn="cn=svc,dc=corp,dc=com",
        bind_password_enc=encrypted_pw.decode(),
        base_dn="dc=corp,dc=com",
        user_search_filter="(mail={input})",
    )


def test_decrypts_bind_password_round_trip() -> None:
    cipher = encrypt(b"correct-horse-staple", SECRET)
    row = _row(["ldaps://dc01:636"], cipher)
    cfg = LdapProviderConfig.from_row(row, SECRET)
    assert cfg.bind_password == "correct-horse-staple"


def test_validate_rejects_malformed_uri() -> None:
    with pytest.raises(ValueError, match="invalid server URI"):
        validate_server_uris(["not-a-url"])


def test_validate_accepts_ldap_and_ldaps_schemes() -> None:
    validate_server_uris(["ldap://dc01:389", "ldaps://dc02:636"])
