"""Starter Cortex-shim analyzer factories.

Each factory returns a CortexAnalyzerAdapter wired up with the right
datatypes + config. The actual Cortex-Analyzers scripts (GPL) are not
bundled here; the operator points us at their local clones via the
program argv. Shared shape so the runner registry can register them
all uniformly."""

from __future__ import annotations

from dataclasses import dataclass

from adhkar.analyzers.cortex_shim import CortexAnalyzerAdapter, CortexAnalyzerSpec


@dataclass(frozen=True, slots=True)
class CortexStarterConfig:
    api_key: str
    program: tuple[str, ...]
    timeout_seconds: float = 60.0


def build_abuseipdb_analyzer(cfg: CortexStarterConfig) -> CortexAnalyzerAdapter:
    spec = CortexAnalyzerSpec(
        name="AbuseIPDB_GetReport_1_0",
        description="Look up an IP's AbuseIPDB reputation score and report history.",
        supported_types=frozenset({"ip"}),
        program=cfg.program,
        config={"key": cfg.api_key, "days": 30, "verbose": True},
        timeout_seconds=cfg.timeout_seconds,
    )
    return CortexAnalyzerAdapter(spec)


def build_shodan_analyzer(cfg: CortexStarterConfig) -> CortexAnalyzerAdapter:
    spec = CortexAnalyzerSpec(
        name="Shodan_Host_1_0",
        description="Look up an IP's open ports, banners, and Shodan tags.",
        supported_types=frozenset({"ip"}),
        program=cfg.program,
        config={"key": cfg.api_key},
        timeout_seconds=cfg.timeout_seconds,
    )
    return CortexAnalyzerAdapter(spec)


def build_urlscan_analyzer(cfg: CortexStarterConfig) -> CortexAnalyzerAdapter:
    spec = CortexAnalyzerSpec(
        name="URLScan_Search_1_0",
        description="Search urlscan.io for prior scans of a URL or domain.",
        supported_types=frozenset({"url", "domain"}),
        program=cfg.program,
        config={"key": cfg.api_key, "service": "search"},
        timeout_seconds=cfg.timeout_seconds,
    )
    return CortexAnalyzerAdapter(spec)


def build_hybridanalysis_analyzer(cfg: CortexStarterConfig) -> CortexAnalyzerAdapter:
    spec = CortexAnalyzerSpec(
        name="HybridAnalysis_GetReport_1_0",
        description="Look up a file hash on Hybrid Analysis for sandbox detonation data.",
        supported_types=frozenset({"hash"}),
        program=cfg.program,
        config={"secret": cfg.api_key},
        timeout_seconds=cfg.timeout_seconds,
    )
    return CortexAnalyzerAdapter(spec)
