"""Analyzer base class.

Concrete analyzers implement `run(data_type, data) -> AnalyzerResult`.
The runner loads them via the registry.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class AnalyzerResult:
    """Standardized analyzer output."""

    summary: dict[str, Any]
    """Short human-readable summary (e.g. {'taxonomies': [...]}, {'level':'malicious'})."""
    full: dict[str, Any]
    """Full raw output."""


class Analyzer(ABC):
    """Abstract analyzer plugin."""

    name: str
    """Unique key (e.g. 'DNS_Resolver_1_0', 'Mock_Reputation_0_1')."""

    supported_types: frozenset[str]
    """Observable data_types this analyzer accepts (e.g. {'ip','domain'})."""

    description: str = ""

    @abstractmethod
    async def run(self, data_type: str, data: str) -> AnalyzerResult: ...
