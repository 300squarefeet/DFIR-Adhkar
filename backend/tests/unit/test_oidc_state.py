"""OIDC state HMAC + provider loader tests."""

from __future__ import annotations

import json

from adhkar.auth.oidc import (
    load_providers,
    new_nonce,
    sign_state,
    verify_state,
)


def test_state_roundtrip_matches_signing_secret() -> None:
    secret = "k" * 32
    state = {"nonce": new_nonce(), "provider": "okta", "return_to": "/dashboard"}
    encoded = sign_state(secret, state)
    decoded = verify_state(secret, encoded)
    assert decoded == state


def test_state_rejected_with_wrong_secret() -> None:
    encoded = sign_state("s1" * 16, {"a": "b"})
    assert verify_state("different" * 4, encoded) is None


def test_state_rejected_when_tampered() -> None:
    encoded = sign_state("k" * 32, {"a": "b"})
    body, mac = encoded.rsplit("|", 1)
    bad = body.replace('"b"', '"c"') + "|" + mac
    assert verify_state("k" * 32, bad) is None


def test_state_rejected_when_missing_separator() -> None:
    assert verify_state("k" * 32, "no-pipe-here") is None


def test_load_providers_empty_when_setting_empty(monkeypatch) -> None:
    monkeypatch.setenv("ADHKAR_SECRET_KEY", "x" * 32)
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h/db")
    monkeypatch.setenv("REDIS_URL", "redis://h:6379/0")
    monkeypatch.setenv("ADHKAR_OIDC_PROVIDERS_JSON", "")
    from adhkar.core.settings import Settings, get_settings

    get_settings.cache_clear()
    assert load_providers(Settings()) == {}


def test_load_providers_parses_two(monkeypatch) -> None:
    monkeypatch.setenv("ADHKAR_SECRET_KEY", "x" * 32)
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h/db")
    monkeypatch.setenv("REDIS_URL", "redis://h:6379/0")
    monkeypatch.setenv(
        "ADHKAR_OIDC_PROVIDERS_JSON",
        json.dumps(
            {
                "okta": {
                    "client_id": "id1",
                    "client_secret": "s1",
                    "discovery_url": "https://acme.okta.com/.well-known/openid-configuration",
                },
                "google": {
                    "client_id": "id2",
                    "client_secret": "s2",
                    "discovery_url": "https://accounts.google.com/.well-known/openid-configuration",
                    "scopes": ["openid", "email"],
                },
            }
        ),
    )
    from adhkar.core.settings import Settings, get_settings

    get_settings.cache_clear()
    providers = load_providers(Settings())
    assert set(providers) == {"okta", "google"}
    assert providers["google"].scopes == ("openid", "email")


def test_load_providers_skips_malformed_entries(monkeypatch) -> None:
    monkeypatch.setenv("ADHKAR_SECRET_KEY", "x" * 32)
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h/db")
    monkeypatch.setenv("REDIS_URL", "redis://h:6379/0")
    monkeypatch.setenv(
        "ADHKAR_OIDC_PROVIDERS_JSON",
        json.dumps(
            {
                "incomplete": {"client_id": "x"},  # missing secret + discovery
                "ok": {
                    "client_id": "a",
                    "client_secret": "b",
                    "discovery_url": "https://x/.well-known/openid-configuration",
                },
            }
        ),
    )
    from adhkar.core.settings import Settings, get_settings

    get_settings.cache_clear()
    providers = load_providers(Settings())
    assert set(providers) == {"ok"}
