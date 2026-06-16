"""MaxMind GeoIP analyzer tests (no real DB; package may be absent)."""

from __future__ import annotations

import pytest
from adhkar.analyzers.maxmind_geoip import MaxMindGeoIpAnalyzer, MaxMindGeoIpConfig


@pytest.mark.asyncio
async def test_rejects_unsupported_datatype() -> None:
    a = MaxMindGeoIpAnalyzer(MaxMindGeoIpConfig())
    r = await a.run("url", "https://x")
    assert "unsupported_dataType" in r.summary["errorMessage"]


@pytest.mark.asyncio
async def test_returns_structured_error_when_no_dbs_configured() -> None:
    a = MaxMindGeoIpAnalyzer(MaxMindGeoIpConfig())
    r = await a.run("ip", "8.8.8.8")
    # Either maxminddb is missing OR no DB paths supplied → either way we
    # MUST return a structured error, never raise.
    assert "errorMessage" in r.summary


@pytest.mark.asyncio
async def test_supported_types_is_ip_only() -> None:
    a = MaxMindGeoIpAnalyzer(MaxMindGeoIpConfig())
    assert a.supported_types == frozenset({"ip"})
