"""Feeder base class.

Concrete feeders pull from an external system (MISP, IMAP, Graph, SIEM
search API) and yield AlertPayload objects. The runner converts those into
Alert rows via the same upsert path the public /v1/alerts endpoint uses,
so dedup-by-sourceRef works uniformly."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class AlertPayload:
    """Normalized inbound alert. The runner picks an org_id and persists."""

    type: str
    source: str
    source_ref: str
    title: str
    description: str | None = None
    severity: int = 2
    tlp: str = "amber"
    pap: str = "amber"
    date: datetime | None = None
    tags: list[str] = field(default_factory=list)
    custom_fields: dict[str, Any] = field(default_factory=dict)
    raw_payload: dict[str, Any] | None = None


class Feeder(ABC):
    """Abstract feeder plugin."""

    name: str
    """Unique key (e.g. 'misp.events.v1', 'imap.mailbox.v1')."""

    description: str = ""

    @abstractmethod
    async def poll(self) -> AsyncIterator[AlertPayload]:
        """Yield zero-or-more AlertPayload objects on each call."""
        if False:
            yield  # pragma: no cover — keeps type-checker happy on subclasses
