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


def test_render_filter_hex_escapes_per_rfc4515() -> None:
    # Build a minimal cfg directly (no row) for filter test
    from uuid import uuid4

    from adhkar.auth.ldap_provider import LdapProviderConfig

    cfg = LdapProviderConfig(
        id=uuid4(),
        name="t",
        server_uris=["ldaps://x:636"],
        bind_dn="x",
        bind_password="x",
        base_dn="x",
        user_search_filter="(mail={input})",
        user_id_attr="x",
        user_email_attr="x",
        user_display_name_attr="x",
        group_membership_attr="x",
        tls_required=True,
        allow_insecure=False,
        priority=100,
        timeout_seconds=5,
    )
    assert cfg.render_filter("a*b(c)d") == r"(mail=a\2ab\28c\29d)"
    assert cfg.render_filter("plain@corp.com") == "(mail=plain@corp.com)"
