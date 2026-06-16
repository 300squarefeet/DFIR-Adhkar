"""VirusTotal-via-Cortex factory tests."""

from __future__ import annotations

import pytest
from adhkar.analyzers.cortex_shim import CortexAnalyzerAdapter
from adhkar.analyzers.virustotal_cortex import (
    VirusTotalConfig,
    build_virustotal_analyzer,
)


def test_builds_adapter_with_expected_datatypes() -> None:
    a = build_virustotal_analyzer(
        VirusTotalConfig(api_key="vt-test", program=("/bin/true",), rate_limit_per_minute=4)
    )
    assert isinstance(a, CortexAnalyzerAdapter)
    assert a.supported_types == frozenset({"ip", "domain", "url", "hash"})
    assert a.spec.config["key"] == "vt-test"
    assert a.spec.config["rate_limit"] == 4
    assert a.spec.config["service"] == "GetReport"
    assert a.spec.timeout_seconds == 60.0


@pytest.mark.asyncio
async def test_rejects_unsupported_datatype_via_adapter() -> None:
    a = build_virustotal_analyzer(VirusTotalConfig(api_key="k", program=("/bin/true",)))
    r = await a.run("email", "x@y")
    assert "unsupported_dataType" in r.summary["errorMessage"]
