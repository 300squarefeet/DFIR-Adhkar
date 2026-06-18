"""End-to-end SAML ACS test: signed assertion -> 200 + access_token.

Boots Postgres+Redis+MinIO via the session-scoped `services` fixture,
applies Alembic migrations once per session, then POSTs the
valid_response.xml fixture to /v1/auth/saml/test/acs and asserts the
issued token round-trip plus a saml_login audit row."""

from __future__ import annotations

import asyncio
import base64
import json
import pathlib
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from freezegun import freeze_time
from httpx import ASGITransport, AsyncClient

FIXTURES = pathlib.Path(__file__).parent.parent / "unit" / "fixtures" / "saml"
FROZEN_NOW = datetime(2026, 6, 17, 12, 0, 0, tzinfo=UTC)


@pytest_asyncio.fixture
async def app_with_verifier(services, monkeypatch):
    """Boot the app against real Postgres+Redis with a SAML verifier wired
    into app.state. Migrations apply once per session via _migrations_applied."""
    monkeypatch.setenv("DATABASE_URL", services["database_url"])
    monkeypatch.setenv("REDIS_URL", services["redis_url"])
    monkeypatch.setenv("ADHKAR_SECRET_KEY", "x" * 32)
    monkeypatch.setenv(
        "ADHKAR_SAML_PROVIDERS_JSON",
        json.dumps(
            {
                "test": {
                    "idp_entity_id": "https://idp.test/saml/metadata",
                    "idp_sso_url": "https://idp.test/saml/sso",
                    "sp_entity_id": "https://adhkar.test/api/v1/auth/saml/test/metadata",
                    "acs_url": "https://adhkar.test/v1/auth/saml/test/acs",
                    "metadata_url": "https://idp.test/metadata",
                }
            }
        ),
    )
    from adhkar.core.settings import get_settings

    get_settings.cache_clear()

    from alembic import command
    from alembic.config import Config

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", services["database_url"])
    await asyncio.to_thread(command.upgrade, cfg, "head")

    from adhkar.auth.saml import SamlProviderConfig
    from adhkar.auth.saml_verifier import build_verifier_from_metadata_xml
    from adhkar.core.settings import Settings
    from adhkar.main import create_app

    app = create_app(Settings())
    cfg_obj = SamlProviderConfig(
        name="test",
        idp_entity_id="https://idp.test/saml/metadata",
        idp_sso_url="https://idp.test/saml/sso",
        sp_entity_id="https://adhkar.test/api/v1/auth/saml/test/metadata",
        acs_url="https://adhkar.test/v1/auth/saml/test/acs",
        metadata_url="https://idp.test/metadata",
        wanted_attributes={"email": "mail", "display_name": "displayName"},
    )
    metadata_xml = (FIXTURES / "valid_idp_metadata.xml").read_text()
    app.state.saml_verifiers = {"test": build_verifier_from_metadata_xml(cfg_obj, metadata_xml)}
    yield app


def _b64(name: str) -> str:
    return base64.b64encode((FIXTURES / name).read_bytes()).decode()


@pytest.mark.integration
@pytest.mark.asyncio
@freeze_time(FROZEN_NOW)
async def test_acs_with_valid_response_issues_access_token(app_with_verifier) -> None:
    transport = ASGITransport(app=app_with_verifier)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.post(
            "/v1/auth/saml/test/acs",
            data={"SAMLResponse": _b64("valid_response.xml"), "RelayState": ""},
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "access_token" in body and isinstance(body["access_token"], str)
    assert body["token_type"] == "bearer"
    assert body["user_id"]
