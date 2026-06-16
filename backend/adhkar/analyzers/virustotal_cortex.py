"""VirusTotal analyzer built on the Cortex shim.

We don't ship the VirusTotal Cortex script itself (it's GPL and lives in
TheHive-Project/Cortex-Analyzers); the operator points us at their copy
via VTOTAL_PROGRAM. This factory returns a CortexAnalyzerAdapter wired
up with the right datatypes (ip/domain/url/hash) and api_key config."""

from __future__ import annotations

from dataclasses import dataclass

from adhkar.analyzers.cortex_shim import CortexAnalyzerAdapter, CortexAnalyzerSpec


@dataclass(frozen=True, slots=True)
class VirusTotalConfig:
    api_key: str
    program: tuple[str, ...]
    """e.g. ('python', '/opt/Cortex-Analyzers/analyzers/VirusTotal/virustotal.py')"""
    rate_limit_per_minute: int = 4
    """VirusTotal Public API default; tighten if you're on the paid tier."""


def build_virustotal_analyzer(cfg: VirusTotalConfig) -> CortexAnalyzerAdapter:
    spec = CortexAnalyzerSpec(
        name="VirusTotal_GetReport_3_1",
        description="Look up file/url/domain/ip reputation on VirusTotal v3.",
        supported_types=frozenset({"ip", "domain", "url", "hash"}),
        program=cfg.program,
        config={
            "key": cfg.api_key,
            "polling_interval": 60,
            "rate_limit": cfg.rate_limit_per_minute,
            "service": "GetReport",
        },
        timeout_seconds=60.0,
    )
    return CortexAnalyzerAdapter(spec)
