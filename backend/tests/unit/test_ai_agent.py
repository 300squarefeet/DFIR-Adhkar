"""ToolUse agent loop unit tests."""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from adhkar.ai.agent import _parse_tool_calls, run_agent
from adhkar.ai.router import LlmProvider, LlmRequest, LlmResponse, get_router


class _ScriptedProvider(LlmProvider):
    name = "scripted"

    def __init__(self, replies: list[str]) -> None:
        self._replies = replies
        self._i = 0

    async def generate(self, req: LlmRequest) -> LlmResponse:
        text = self._replies[min(self._i, len(self._replies) - 1)]
        self._i += 1
        return LlmResponse(
            text=text,
            model=req.model or "scripted",
            provider=self.name,
            input_tokens=1,
            output_tokens=len(text.split()),
            raw={},
        )


def test_parse_tool_calls_picks_up_one_envelope() -> None:
    text = 'Let me check. <tool_use>{"name":"search_cases","arguments":{"limit":5}}</tool_use> ok.'
    parsed = _parse_tool_calls(text)
    assert parsed == [("search_cases", {"limit": 5})]


def test_parse_tool_calls_ignores_malformed_json() -> None:
    text = "<tool_use>not json</tool_use>"
    assert _parse_tool_calls(text) == []


def test_parse_tool_calls_handles_multiple_envelopes() -> None:
    text = (
        '<tool_use>{"name":"search_cases","arguments":{}}</tool_use>'
        '<tool_use>{"name":"search_alerts","arguments":{}}</tool_use>'
    )
    parsed = _parse_tool_calls(text)
    assert [p[0] for p in parsed] == ["search_cases", "search_alerts"]


@pytest.mark.asyncio
async def test_agent_stops_on_first_non_tool_message() -> None:
    get_router().register(_ScriptedProvider(["All good — no tool needed."]))
    db = AsyncMock()
    run = await run_agent(
        db,
        uuid4(),
        system="be helpful",
        user_prompt="hi",
        provider="scripted",
        max_steps=3,
    )
    assert run.final_text == "All good — no tool needed."
    assert run.tool_calls == 0
    assert [s.role for s in run.steps] == ["user", "assistant"]


@pytest.mark.asyncio
async def test_agent_invokes_tool_then_stops() -> None:
    # First reply asks for a tool, second is a plain answer.
    get_router().register(
        _ScriptedProvider(
            [
                '<tool_use>{"name":"unknown_tool","arguments":{}}</tool_use>',
                "Based on the tool error, here is the final answer.",
            ]
        )
    )
    db = AsyncMock()
    run = await run_agent(
        db,
        uuid4(),
        system="be helpful",
        user_prompt="please look it up",
        provider="scripted",
        max_steps=3,
    )
    assert run.tool_calls == 1
    assert "final answer" in run.final_text
    assert any(s.role == "tool" for s in run.steps)
    tool_step = next(s for s in run.steps if s.role == "tool")
    assert "unknown_tool" in tool_step.content


@pytest.mark.asyncio
async def test_agent_respects_max_steps() -> None:
    # Always returns a tool call to an unknown tool (no DB needed).
    get_router().register(
        _ScriptedProvider(['<tool_use>{"name":"nope","arguments":{}}</tool_use>'] * 10)
    )
    db = AsyncMock()
    run = await run_agent(
        db,
        uuid4(),
        system="loop forever",
        user_prompt="go",
        provider="scripted",
        max_steps=2,
    )
    # bounded by max_steps iterations, 1 tool call per iteration
    assert run.tool_calls == 2
