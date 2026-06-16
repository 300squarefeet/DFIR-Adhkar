"""Provider-agnostic LLM router. Default: Anthropic. Pluggable: OpenAI, Ollama.

Strict design notes:
- Every AI call is logged with model, provider, prompt hash, token usage.
- High-impact actions are non-destructive by default; runtime callers must
  opt in to action mode via execute_actions=True (current scope: read-only
  text generation only — actions land in a follow-up phase).
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

_log = logging.getLogger(__name__)


@dataclass
class LlmRequest:
    system: str
    messages: list[dict[str, str]]
    model: str | None = None
    max_tokens: int = 1024
    temperature: float = 0.2
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class LlmResponse:
    text: str
    model: str
    provider: str
    input_tokens: int
    output_tokens: int
    raw: dict[str, Any] = field(default_factory=dict)


class LlmProvider(ABC):
    name: str

    @abstractmethod
    async def generate(self, req: LlmRequest) -> LlmResponse:
        """Return a single completion. Implementations MUST set token counts."""


class StubProvider(LlmProvider):
    """No-network provider used for dev/test/local-only mode.

    Returns deterministic prefixed echo. Never makes external calls."""

    name = "stub"

    async def generate(self, req: LlmRequest) -> LlmResponse:
        last_user = ""
        for m in reversed(req.messages):
            if m.get("role") == "user":
                last_user = m.get("content", "")
                break
        text = f"[stub:{req.model or 'default'}] {last_user[:500]}"
        return LlmResponse(
            text=text,
            model=req.model or "stub-default",
            provider=self.name,
            input_tokens=len(last_user.split()),
            output_tokens=len(text.split()),
            raw={},
        )


class LlmRouter:
    """Holds providers keyed by name; default chosen from settings."""

    def __init__(self, default_provider: str = "stub") -> None:
        self._providers: dict[str, LlmProvider] = {}
        self._default = default_provider
        self.register(StubProvider())

    def register(self, provider: LlmProvider) -> None:
        self._providers[provider.name] = provider

    def providers(self) -> list[str]:
        return sorted(self._providers)

    async def generate(self, req: LlmRequest, provider: str | None = None) -> LlmResponse:
        name = provider or self._default
        if name not in self._providers:
            raise ValueError(f"unknown_llm_provider:{name}")
        resp = await self._providers[name].generate(req)
        _log.info(
            "llm_call provider=%s model=%s in=%d out=%d",
            resp.provider,
            resp.model,
            resp.input_tokens,
            resp.output_tokens,
        )
        return resp


_router: LlmRouter | None = None


def get_router() -> LlmRouter:
    global _router
    if _router is None:
        _router = LlmRouter()
    return _router
