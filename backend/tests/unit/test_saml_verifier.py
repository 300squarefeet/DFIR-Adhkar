"""SamlVerifier - fixture-based unit tests."""

from __future__ import annotations

import base64
import pathlib
from datetime import UTC, datetime

import fakeredis.aioredis
import pytest
import pytest_asyncio
from adhkar.auth.saml import SamlProviderConfig
from adhkar.auth.saml_verifier import SamlVerifier, build_verifier_from_metadata_xml
from freezegun import freeze_time

FIXTURES = pathlib.Path(__file__).parent / "fixtures" / "saml"
FROZEN_NOW = datetime(2026, 6, 17, 12, 0, 0, tzinfo=UTC)


def _b64(name: str) -> str:
    return base64.b64encode((FIXTURES / name).read_bytes()).decode()


@pytest.fixture
def cfg() -> SamlProviderConfig:
    return SamlProviderConfig(
        name="test",
        idp_entity_id="https://idp.test/saml/metadata",
        idp_sso_url="https://idp.test/saml/sso",
        sp_entity_id="https://adhkar.test/api/v1/auth/saml/test/metadata",
        acs_url="https://adhkar.test/v1/auth/saml/test/acs",
        metadata_url="https://idp.test/saml/metadata",
        wanted_attributes={"email": "mail", "display_name": "displayName"},
    )


@pytest_asyncio.fixture
async def redis() -> fakeredis.aioredis.FakeRedis:
    r = fakeredis.aioredis.FakeRedis()
    try:
        yield r
    finally:
        await r.aclose()


@pytest.fixture
def verifier(cfg: SamlProviderConfig) -> SamlVerifier:
    metadata_xml = (FIXTURES / "valid_idp_metadata.xml").read_text()
    return build_verifier_from_metadata_xml(cfg, metadata_xml)


@pytest.mark.asyncio
@freeze_time(FROZEN_NOW)
async def test_valid_response_returns_claims(
    verifier: SamlVerifier,
    redis: fakeredis.aioredis.FakeRedis,
) -> None:
    claims = await verifier.verify_and_extract(_b64("valid_response.xml"), redis=redis)
    assert claims.email == "soc@example.test"
    assert claims.display_name == "SOC Bot"
    assert claims.name_id == "soc@example.test"
    assert claims.assertion_id == "assertion-valid"
    assert claims.not_on_or_after > FROZEN_NOW
