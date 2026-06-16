"""Starter Cortex-shim factories share a shape — exercise each one."""

from __future__ import annotations

import pytest
from adhkar.analyzers.cortex_shim import CortexAnalyzerAdapter
from adhkar.analyzers.starter_factories import (
    CortexStarterConfig,
    build_abuseipdb_analyzer,
    build_hybridanalysis_analyzer,
    build_shodan_analyzer,
    build_urlscan_analyzer,
)


def _cfg() -> CortexStarterConfig:
    return CortexStarterConfig(api_key="tok", program=("/bin/true",))


def test_abuseipdb_supports_ip_only() -> None:
    a = build_abuseipdb_analyzer(_cfg())
    assert isinstance(a, CortexAnalyzerAdapter)
    assert a.supported_types == frozenset({"ip"})
    assert a.spec.config["key"] == "tok"
    assert a.spec.config["days"] == 30


def test_shodan_supports_ip_only() -> None:
    a = build_shodan_analyzer(_cfg())
    assert a.supported_types == frozenset({"ip"})
    assert a.spec.config == {"key": "tok"}


def test_urlscan_supports_url_and_domain() -> None:
    a = build_urlscan_analyzer(_cfg())
    assert a.supported_types == frozenset({"url", "domain"})
    assert a.spec.config["service"] == "search"


def test_hybridanalysis_uses_secret_field_for_api_key() -> None:
    a = build_hybridanalysis_analyzer(_cfg())
    assert a.supported_types == frozenset({"hash"})
    # HA Cortex script uses 'secret' rather than 'key' — preserve naming.
    assert a.spec.config["secret"] == "tok"


@pytest.mark.asyncio
async def test_every_factory_rejects_unsupported_datatype() -> None:
    factories = [
        (build_abuseipdb_analyzer, "url"),
        (build_shodan_analyzer, "url"),
        (build_urlscan_analyzer, "ip"),
        (build_hybridanalysis_analyzer, "ip"),
    ]
    for factory, bad_type in factories:
        a = factory(_cfg())
        r = await a.run(bad_type, "anything")
        assert "unsupported_dataType" in r.summary["errorMessage"]
