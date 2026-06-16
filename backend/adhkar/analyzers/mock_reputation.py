"""Mock reputation analyzer: deterministic toy output for offline testing."""

from __future__ import annotations

import hashlib

from adhkar.analyzers.base import Analyzer, AnalyzerResult


class MockReputation(Analyzer):
    name = "Mock_Reputation_0_1"
    supported_types = frozenset({"ip", "domain", "url", "hash"})
    description = "Deterministic mock reputation score. Phase 0 offline-friendly."

    async def run(self, data_type: str, data: str) -> AnalyzerResult:
        h = hashlib.sha256(data.encode()).hexdigest()
        score = int(h[:2], 16)  # 0-255
        level = "malicious" if score > 200 else "suspicious" if score > 128 else "clean"
        return AnalyzerResult(
            summary={"level": level, "score": score},
            full={"data_type": data_type, "data": data, "hash": h, "score": score, "level": level},
        )
