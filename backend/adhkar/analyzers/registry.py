"""Analyzer registry — keeps a global mapping of name → Analyzer instance."""

from __future__ import annotations

from adhkar.analyzers.base import Analyzer


class AnalyzerRegistry:
    """In-process analyzer registry."""

    def __init__(self) -> None:
        self._analyzers: dict[str, Analyzer] = {}

    def register(self, analyzer: Analyzer) -> None:
        if analyzer.name in self._analyzers:
            raise ValueError(f"analyzer already registered: {analyzer.name}")
        self._analyzers[analyzer.name] = analyzer

    def get(self, name: str) -> Analyzer | None:
        return self._analyzers.get(name)

    def list_for_type(self, data_type: str) -> list[Analyzer]:
        return [a for a in self._analyzers.values() if data_type in a.supported_types]

    def all(self) -> list[Analyzer]:
        return list(self._analyzers.values())


_global_registry = AnalyzerRegistry()


def get_registry() -> AnalyzerRegistry:
    return _global_registry
