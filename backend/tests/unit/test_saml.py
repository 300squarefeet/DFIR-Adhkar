"""SAML provider loader + assertion extractor unit tests."""

from __future__ import annotations

import json

from adhkar.auth.saml import extract_assertion_attributes, load_saml_providers


def test_load_saml_providers_empty(monkeypatch) -> None:
    monkeypatch.setenv("ADHKAR_SECRET_KEY", "x" * 32)
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h/db")
    monkeypatch.setenv("REDIS_URL", "redis://h:6379/0")
    monkeypatch.setenv("ADHKAR_SAML_PROVIDERS_JSON", "")
    from adhkar.core.settings import Settings, get_settings

    get_settings.cache_clear()
    assert load_saml_providers(Settings()) == {}


def test_load_saml_providers_parses_entry(monkeypatch) -> None:
    monkeypatch.setenv("ADHKAR_SECRET_KEY", "x" * 32)
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h/db")
    monkeypatch.setenv("REDIS_URL", "redis://h:6379/0")
    monkeypatch.setenv(
        "ADHKAR_SAML_PROVIDERS_JSON",
        json.dumps(
            {
                "okta": {
                    "idp_entity_id": "http://www.okta.com/exk-x",
                    "idp_sso_url": "https://acme.okta.com/app/sso/saml",
                    "sp_entity_id": "https://adhkar/api/v1/auth/saml/okta/metadata",
                    "acs_url": "https://adhkar/v1/auth/saml/okta/acs",
                }
            }
        ),
    )
    from adhkar.core.settings import Settings, get_settings

    get_settings.cache_clear()
    providers = load_saml_providers(Settings())
    assert "okta" in providers
    assert providers["okta"].idp_sso_url.startswith("https://acme.okta.com")


def test_load_saml_providers_skips_malformed(monkeypatch) -> None:
    monkeypatch.setenv("ADHKAR_SECRET_KEY", "x" * 32)
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h/db")
    monkeypatch.setenv("REDIS_URL", "redis://h:6379/0")
    monkeypatch.setenv(
        "ADHKAR_SAML_PROVIDERS_JSON",
        json.dumps(
            {
                "broken": {"idp_entity_id": "x"},
                "ok": {
                    "idp_entity_id": "a",
                    "idp_sso_url": "b",
                    "sp_entity_id": "c",
                    "acs_url": "d",
                },
            }
        ),
    )
    from adhkar.core.settings import Settings, get_settings

    get_settings.cache_clear()
    providers = load_saml_providers(Settings())
    assert set(providers) == {"ok"}


_SAMPLE_SAML = """<?xml version="1.0"?>
<saml:Assertion xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion">
  <saml:Subject>
    <saml:NameID>soc@example.test</saml:NameID>
  </saml:Subject>
  <saml:AttributeStatement>
    <saml:Attribute Name="email">
      <saml:AttributeValue>soc@example.test</saml:AttributeValue>
    </saml:Attribute>
    <saml:Attribute Name="name">
      <saml:AttributeValue>SOC Bot</saml:AttributeValue>
    </saml:Attribute>
  </saml:AttributeStatement>
</saml:Assertion>"""


def test_extract_assertion_pulls_email_and_name() -> None:
    attrs = extract_assertion_attributes(_SAMPLE_SAML)
    assert attrs["email"] == "soc@example.test"
    assert attrs["name"] == "SOC Bot"


def test_extract_assertion_returns_empty_on_malformed_xml() -> None:
    assert extract_assertion_attributes("<not xml") == {}


def test_extract_assertion_picks_up_nameid_when_email_missing() -> None:
    no_email = _SAMPLE_SAML.replace(
        '<saml:Attribute Name="email">',
        '<saml:Attribute Name="other">',
    )
    attrs = extract_assertion_attributes(no_email)
    assert attrs.get("NameID") == "soc@example.test"
