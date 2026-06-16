"""ToolUse agent loop.

Given a user prompt, an LLM provider, and a max-step budget, the loop:
1. Asks the LLM with the full tool catalog attached.
2. If the LLM returns a tool_call request, dispatches it via TOOL_CATALOG,
   appends the result to the transcript, and loops.
3. Stops on the first message that is not a tool call OR when max_steps
   is hit (returns the partial transcript).

The StubProvider in `adhkar.ai.router` does not emit tool calls, so this
agent collapses to a single round on the stub — the runtime stays runnable
offline."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from adhkar.ai.router import LlmRequest, LlmResponse, get_router
from adhkar.ai.tools import TOOL_CATALOG, get_tool


@dataclass
class AgentStep:
    role: str  # 'user' | 'assistant' | 'tool'
    content: str
    tool_name: str | None = None
    tool_args: dict[str, Any] | None = None


@dataclass
class AgentRun:
    steps: list[AgentStep] = field(default_factory=list)
    final_text: str = ""
    tool_calls: int = 0


# Tool-call envelope the LLM emits when it wants to invoke a tool.
# Format the stub will never produce; concrete provider adapters parse
# their native tool_use blocks and translate into this same envelope.
_TOOL_RE = re.compile(r"<tool_use>\s*(\{.*?\})\s*</tool_use>", re.DOTALL | re.IGNORECASE)


def _parse_tool_calls(text: str) -> list[tuple[str, dict[str, Any]]]:
    out: list[tuple[str, dict[str, Any]]] = []
    for m in _TOOL_RE.finditer(text):
        try:
            obj = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
        name = obj.get("name")
        args = obj.get("arguments") or {}
        if isinstance(name, str) and isinstance(args, dict):
            out.append((name, args))
    return out


async def run_agent(
    db: AsyncSession,
    org_id: UUID,
    system: str,
    user_prompt: str,
    *,
    provider: str | None = None,
    model: str | None = None,
    max_steps: int = 5,
) -> AgentRun:
    """Run the tool-use loop. Returns the full transcript + final text."""
    run = AgentRun()
    transcript: list[dict[str, str]] = [{"role": "user", "content": user_prompt}]
    run.steps.append(AgentStep(role="user", content=user_prompt))
    router = get_router()
    tool_catalog_str = json.dumps(
        [
            {"name": t.name, "description": t.description, "input_schema": t.input_schema}
            for t in TOOL_CATALOG
        ]
    )
    augmented_system = (
        system + "\n\nYou may call tools by emitting "
        '<tool_use>{"name":"...","arguments":{...}}</tool_use> blocks. '
        "Available tools:\n" + tool_catalog_str
    )
    for _ in range(max_steps):
        req = LlmRequest(system=augmented_system, messages=transcript, model=model)
        resp: LlmResponse = await router.generate(req, provider=provider)
        text = resp.text
        run.steps.append(AgentStep(role="assistant", content=text))
        tool_calls = _parse_tool_calls(text)
        if not tool_calls:
            run.final_text = text
            return run
        for name, args in tool_calls:
            tool = get_tool(name)
            if tool is None:
                tool_output = f"error: unknown_tool:{name}"
            else:
                try:
                    tool_output = await tool.handler(db, org_id, args)
                except Exception as e:
                    tool_output = f"error: tool_exception:{type(e).__name__}:{e}"
            run.tool_calls += 1
            run.steps.append(
                AgentStep(role="tool", content=tool_output, tool_name=name, tool_args=args)
            )
            transcript.append(
                {"role": "user", "content": f"<tool_result>{tool_output}</tool_result>"}
            )
    # Hit max_steps with tools still pending. Final text is the last assistant text.
    run.final_text = next((s.content for s in reversed(run.steps) if s.role == "assistant"), "")
    return run
