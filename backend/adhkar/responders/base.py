"""Responder base class + registry.

Responders take action: block an IP, send a Slack/Teams message, create a
ticket, close a case. They are always invoked synchronously from the API
or async via a job queue, and their full input/output is audit-logged.

Safety contracts:
- Responders MUST declare confirm_required: bool. Destructive responders
  (block-ip, close-case-permanent) set True so the UI shows a confirm.
- Responders MUST declare supported_entity_types.
- Responders MUST NOT silently fail. Return a ResponderResult with
  status='failed' + a short message.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class ResponderResult:
    status: str  # 'ok' | 'failed'
    summary: str
    details: dict[str, Any] = field(default_factory=dict)


class Responder(ABC):
    name: str
    description: str
    supported_entity_types: frozenset[str]
    """e.g. {'case','alert','observable','task'}"""
    confirm_required: bool = False

    @abstractmethod
    async def run(
        self, entity_type: str, entity_id: str, payload: dict[str, Any]
    ) -> ResponderResult: ...


class ResponderRegistry:
    def __init__(self) -> None:
        self._items: dict[str, Responder] = {}

    def register(self, r: Responder) -> None:
        self._items[r.name] = r

    def get(self, name: str) -> Responder | None:
        return self._items.get(name)

    def all(self) -> list[Responder]:
        return sorted(self._items.values(), key=lambda r: r.name)


_registry = ResponderRegistry()


def get_responder_registry() -> ResponderRegistry:
    return _registry
