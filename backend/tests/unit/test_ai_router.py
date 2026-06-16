"""Phase 8: LLM router + stub provider tests."""

from __future__ import annotations

import pytest
from adhkar.ai.router import LlmRequest, LlmRouter, StubProvider


@pytest.mark.asyncio
async def test_stub_provider_returns_deterministic_echo() -> None:
    p = StubProvider()
    req = LlmRequest(
        system="sys", messages=[{"role": "user", "content": "what is T1059?"}], model="m"
    )
    resp = await p.generate(req)
    assert resp.provider == "stub"
    assert "what is T1059?" in resp.text
    assert resp.input_tokens > 0
    assert resp.output_tokens > 0


@pytest.mark.asyncio
async def test_router_uses_default_provider() -> None:
    r = LlmRouter()
    assert "stub" in r.providers()
    resp = await r.generate(LlmRequest(system="s", messages=[{"role": "user", "content": "hi"}]))
    assert resp.provider == "stub"


@pytest.mark.asyncio
async def test_router_unknown_provider_raises() -> None:
    r = LlmRouter()
    with pytest.raises(ValueError, match="unknown_llm_provider"):
        await r.generate(
            LlmRequest(system="", messages=[{"role": "user", "content": "x"}]),
            provider="does-not-exist",
        )
