"""LdapClient: thin wrapper over ldap3 — mocked via MockSyncStrategy."""

from __future__ import annotations

import pytest
from adhkar.auth.ldap_client import LdapClient
from adhkar.auth.ldap_errors import LdapConnectionError, LdapInvalidCredentials
from ldap3 import MOCK_SYNC, OFFLINE_AD_2012_R2, Connection, Server

SVC_DN = "cn=svc,dc=corp,dc=com"
SVC_PW = "svc-pw"
ALICE_DN = "cn=alice,ou=users,dc=corp,dc=com"
ALICE_PW = "alice-pw"


@pytest.fixture
def mock_server_with_alice() -> Server:
    server = Server("fake-server", get_info=OFFLINE_AD_2012_R2)
    conn = Connection(server, user=SVC_DN, password=SVC_PW, client_strategy=MOCK_SYNC)
    conn.strategy.add_entry(SVC_DN, {"userPassword": SVC_PW, "objectClass": "person", "cn": "svc"})
    conn.strategy.add_entry(
        ALICE_DN,
        {
            "userPassword": ALICE_PW,
            "objectClass": "person",
            "cn": "alice",
            "mail": "alice@corp.com",
            "memberOf": ["cn=SOC Analysts,ou=Groups,dc=corp,dc=com"],
        },
    )
    return server


def test_bind_and_search_returns_entries(monkeypatch, mock_server_with_alice) -> None:
    client = LdapClient(["ldaps://fake-server:636"], tls_required=True, allow_insecure=False)
    monkeypatch.setattr(
        "adhkar.auth.ldap_client._build_connection",
        lambda uri, bind_dn, bind_pw, tls_required, allow_insecure, timeout: Connection(
            mock_server_with_alice, user=bind_dn, password=bind_pw, client_strategy=MOCK_SYNC
        ),
    )
    entries = client.bind_and_search(
        bind_dn=SVC_DN,
        bind_password=SVC_PW,
        base_dn="dc=corp,dc=com",
        search_filter="(mail=alice@corp.com)",
        attributes=["mail", "memberOf"],
    )
    assert len(entries) == 1
    assert entries[0]["dn"] == ALICE_DN
    assert "alice@corp.com" in entries[0]["attrs"]["mail"]


def test_user_bind_returns_true_on_correct_password(monkeypatch, mock_server_with_alice) -> None:
    client = LdapClient(["ldaps://fake-server:636"], tls_required=True, allow_insecure=False)
    monkeypatch.setattr(
        "adhkar.auth.ldap_client._build_connection",
        lambda uri, bind_dn, bind_pw, tls_required, allow_insecure, timeout: Connection(
            mock_server_with_alice, user=bind_dn, password=bind_pw, client_strategy=MOCK_SYNC
        ),
    )
    assert client.user_bind(ALICE_DN, ALICE_PW) is True


def test_user_bind_returns_false_on_wrong_password(monkeypatch, mock_server_with_alice) -> None:
    client = LdapClient(["ldaps://fake-server:636"], tls_required=True, allow_insecure=False)
    monkeypatch.setattr(
        "adhkar.auth.ldap_client._build_connection",
        lambda uri, bind_dn, bind_pw, tls_required, allow_insecure, timeout: Connection(
            mock_server_with_alice, user=bind_dn, password=bind_pw, client_strategy=MOCK_SYNC
        ),
    )
    assert client.user_bind(ALICE_DN, "wrong-pw") is False


def test_user_bind_rejects_empty_password() -> None:
    client = LdapClient(["ldaps://fake-server:636"], tls_required=True, allow_insecure=False)
    with pytest.raises(LdapInvalidCredentials, match="empty password"):
        client.user_bind(ALICE_DN, "")


def test_bind_raises_connection_error_when_all_uris_unreachable() -> None:
    client = LdapClient(
        ["ldaps://nonexistent.invalid:636"],
        tls_required=True,
        allow_insecure=False,
        timeout_seconds=1,
    )
    with pytest.raises(LdapConnectionError):
        client.bind_and_search(
            bind_dn=SVC_DN,
            bind_password=SVC_PW,
            base_dn="dc=corp,dc=com",
            search_filter="(mail=alice@corp.com)",
            attributes=["mail"],
        )
