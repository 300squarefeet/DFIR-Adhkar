"""Cortex compat shim.

Wraps a TheHive/Cortex-style analyzer (a process that reads JSON from stdin
and writes JSON to stdout) inside our Analyzer ABC. Lets users run existing
Cortex analyzer scripts unmodified under Adhkar.

Cortex input format:
    {
      "data": "<observable>",
      "dataType": "ip|domain|url|hash|...",
      "tlp": 0..3,
      "pap": 0..3,
      "config": { "<key>": "<value>", ... }
    }

Cortex output format:
    {
      "summary": { "taxonomies": [...], ... },
      "full": { ... },
      "artifacts": [ { "dataType": "...", "data": "..." }, ... ],
      "success": true | false,
      "errorMessage": "..."
    }

Security note: this shim runs an external process. The caller (Phase 7b)
is responsible for sandboxing — either Docker isolation per call or a
restricted nsjail/firejail profile. The shim itself is just I/O glue."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any

from adhkar.analyzers.base import Analyzer, AnalyzerResult

_log = logging.getLogger(__name__)

_TLP_LABEL_TO_CORTEX = {"white": 0, "green": 1, "amber": 2, "amber-strict": 2, "red": 3}


@dataclass(frozen=True, slots=True)
class CortexAnalyzerSpec:
    """Manifest of a Cortex analyzer wrapped by the shim."""

    name: str
    description: str
    supported_types: frozenset[str]
    program: tuple[str, ...]
    # e.g. ("python", "/opt/cortex/VirusTotal/virustotal.py")
    config: dict[str, Any]
    timeout_seconds: float = 30.0


class CortexAnalyzerAdapter(Analyzer):
    """Adapter exposing a CortexAnalyzerSpec as an Adhkar Analyzer."""

    def __init__(self, spec: CortexAnalyzerSpec, tlp_label: str = "amber") -> None:
        self.spec = spec
        self.name = spec.name
        self.description = spec.description
        self.supported_types = spec.supported_types
        self._tlp = _TLP_LABEL_TO_CORTEX.get(tlp_label, 2)

    async def run(self, data_type: str, data: str) -> AnalyzerResult:
        if data_type not in self.supported_types:
            return AnalyzerResult(
                summary={"errorMessage": f"unsupported_dataType:{data_type}"},
                full={},
            )
        payload = {
            "data": data,
            "dataType": data_type,
            "tlp": self._tlp,
            "pap": self._tlp,
            "config": self.spec.config,
        }
        try:
            proc = await asyncio.create_subprocess_exec(
                *self.spec.program,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(json.dumps(payload).encode("utf-8")),
                timeout=self.spec.timeout_seconds,
            )
        except TimeoutError:
            return AnalyzerResult(
                summary={"errorMessage": "cortex_analyzer_timeout"},
                full={"timeout_seconds": self.spec.timeout_seconds},
            )
        except FileNotFoundError as e:
            return AnalyzerResult(
                summary={"errorMessage": f"cortex_program_not_found:{e}"},
                full={},
            )
        if proc.returncode != 0:
            return AnalyzerResult(
                summary={
                    "errorMessage": "cortex_exit_nonzero",
                    "returncode": proc.returncode,
                },
                full={"stderr": stderr.decode("utf-8", errors="replace")[-2000:]},
            )
        try:
            parsed = json.loads(stdout.decode("utf-8", errors="replace"))
        except json.JSONDecodeError as e:
            return AnalyzerResult(
                summary={"errorMessage": f"cortex_invalid_json:{e}"},
                full={"raw": stdout.decode("utf-8", errors="replace")[:2000]},
            )
        if not parsed.get("success", True):
            return AnalyzerResult(
                summary={
                    "errorMessage": parsed.get("errorMessage", "cortex_reported_failure"),
                },
                full=parsed,
            )
        return AnalyzerResult(
            summary=parsed.get("summary", {}),
            full=parsed,
        )
