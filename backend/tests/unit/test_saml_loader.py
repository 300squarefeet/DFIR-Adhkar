"""build_verifier_from_metadata_url integration test using respx."""

from __future__ import annotations

import pathlib

import httpx
import pytest
import respx
from adhkar.auth.saml import SamlProviderConfig
from adhkar.auth.saml_verifier import build_verifier_from_metadata_url

FIXTURES = pathlib.Path(__file__).parent / "fixtures" / "saml"


def _cfg(metadata_url: str) -> SamlProviderConfig:
    return SamlProviderConfig(
        name="test",
        idp_entity_id="https://idp.test/saml/metadata",
        idp_sso_url="https://idp.test/saml/sso",
        sp_entity_id="https://adhkar.test/api/v1/auth/saml/test/metadata",
        acs_url="https://adhkar.test/v1/auth/saml/test/acs",
        metadata_url=metadata_url,
    )


@pytest.mark.asyncio
async def test_build_verifier_succeeds_when_metadata_url_reachable() -> None:
    metadata_xml = (FIXTURES / "valid_idp_metadata.xml").read_text()
    with respx.mock:
        respx.get("https://idp.test/metadata.xml").mock(
            return_value=httpx.Response(200, text=metadata_xml)
        )
        verifier = await build_verifier_from_metadata_url(_cfg("https://idp.test/metadata.xml"))
    assert verifier is not None


@pytest.mark.asyncio
async def test_build_verifier_returns_none_when_metadata_unreachable() -> None:
    with respx.mock:
        respx.get("https://idp.test/missing.xml").mock(side_effect=httpx.ConnectError("nope"))
        verifier = await build_verifier_from_metadata_url(_cfg("https://idp.test/missing.xml"))
    assert verifier is None


@pytest.mark.asyncio
async def test_build_verifier_returns_none_on_404() -> None:
    with respx.mock:
        respx.get("https://idp.test/404.xml").mock(return_value=httpx.Response(404))
        verifier = await build_verifier_from_metadata_url(_cfg("https://idp.test/404.xml"))
    assert verifier is None


@pytest.mark.asyncio
async def test_build_verifier_returns_none_when_metadata_url_empty() -> None:
    verifier = await build_verifier_from_metadata_url(_cfg(""))
    assert verifier is None
