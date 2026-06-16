"""Cortex shim unit tests (no real subprocess; we run /bin/cat-style stubs)."""

from __future__ import annotations

import pytest
from adhkar.analyzers.cortex_shim import CortexAnalyzerAdapter, CortexAnalyzerSpec


def _spec(program: tuple[str, ...]) -> CortexAnalyzerSpec:
    return CortexAnalyzerSpec(
        name="Test_Analyzer_0_1",
        description="test",
        supported_types=frozenset({"ip", "domain"}),
        program=program,
        config={},
        timeout_seconds=5.0,
    )


@pytest.mark.asyncio
async def test_rejects_unsupported_datatype() -> None:
    a = CortexAnalyzerAdapter(_spec(("/bin/true",)))
    r = await a.run("url", "https://example.test")
    assert "unsupported_dataType" in r.summary["errorMessage"]


@pytest.mark.asyncio
async def test_program_not_found_returns_error_result() -> None:
    a = CortexAnalyzerAdapter(_spec(("/nonexistent/path/to/cortex/analyzer",)))
    r = await a.run("ip", "1.2.3.4")
    assert "cortex_program_not_found" in r.summary["errorMessage"]


@pytest.mark.asyncio
async def test_successful_json_response_is_parsed() -> None:
    # /bin/sh prints a valid Cortex success payload to stdout
    script = (
        "/bin/sh",
        "-c",
        'cat > /dev/null; echo \'{"success": true, "summary": {"level": "safe"}, '
        '"full": {"score": 0}}\'',
    )
    a = CortexAnalyzerAdapter(_spec(script))
    r = await a.run("ip", "1.2.3.4")
    assert r.summary == {"level": "safe"}
    assert r.full.get("full") == {"score": 0}


@pytest.mark.asyncio
async def test_nonzero_exit_is_captured() -> None:
    script = ("/bin/sh", "-c", "cat > /dev/null; echo boom 1>&2; exit 7")
    a = CortexAnalyzerAdapter(_spec(script))
    r = await a.run("ip", "1.2.3.4")
    assert r.summary["errorMessage"] == "cortex_exit_nonzero"
    assert r.summary["returncode"] == 7


@pytest.mark.asyncio
async def test_invalid_json_output_is_handled() -> None:
    script = ("/bin/sh", "-c", "cat > /dev/null; echo notjson")
    a = CortexAnalyzerAdapter(_spec(script))
    r = await a.run("ip", "1.2.3.4")
    assert "cortex_invalid_json" in r.summary["errorMessage"]
