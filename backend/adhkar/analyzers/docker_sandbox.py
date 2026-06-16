"""Docker-sandboxed analyzer executor.

Runs an analyzer command inside an ephemeral Docker container with:
- read-only root filesystem
- no network (when configured)
- dropped capabilities
- CPU + memory limits
- short timeout enforced by the runner

The container reads the Cortex-style JSON input from stdin and writes
JSON to stdout. The same wire format as CortexAnalyzerAdapter, so the
two can share analyzer scripts.

Requires the `docker` CLI on PATH. No Python docker SDK dependency."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any

from adhkar.analyzers.base import Analyzer, AnalyzerResult

_log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class DockerSandboxSpec:
    name: str
    description: str
    supported_types: frozenset[str]
    image: str
    command: tuple[str, ...] = ()
    config: dict[str, Any] | None = None
    timeout_seconds: float = 30.0
    memory_limit: str = "256m"
    cpus: str = "0.5"
    network: str = "none"  # 'none' | 'bridge'


class DockerSandboxAnalyzer(Analyzer):
    """Adapter that runs an analyzer inside `docker run --rm`."""

    def __init__(self, spec: DockerSandboxSpec) -> None:
        self.spec = spec
        self.name = spec.name
        self.description = spec.description
        self.supported_types = spec.supported_types

    def _docker_argv(self) -> list[str]:
        argv = [
            "docker",
            "run",
            "--rm",
            "-i",
            "--read-only",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            f"--network={self.spec.network}",
            f"--memory={self.spec.memory_limit}",
            f"--cpus={self.spec.cpus}",
            "--tmpfs=/tmp:rw,size=64m,mode=1777",
            self.spec.image,
        ]
        if self.spec.command:
            argv.extend(self.spec.command)
        return argv

    async def run(self, data_type: str, data: str) -> AnalyzerResult:
        if data_type not in self.supported_types:
            return AnalyzerResult(
                summary={"errorMessage": f"unsupported_dataType:{data_type}"},
                full={},
            )
        payload = {
            "data": data,
            "dataType": data_type,
            "tlp": 2,
            "pap": 2,
            "config": self.spec.config or {},
        }
        argv = self._docker_argv()
        try:
            proc = await asyncio.create_subprocess_exec(
                *argv,
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
                summary={"errorMessage": "sandbox_timeout"},
                full={"timeout_seconds": self.spec.timeout_seconds},
            )
        except FileNotFoundError:
            return AnalyzerResult(
                summary={"errorMessage": "docker_cli_not_found"},
                full={},
            )
        if proc.returncode != 0:
            tail = stderr.decode("utf-8", errors="replace")[-2000:]
            return AnalyzerResult(
                summary={
                    "errorMessage": "sandbox_exit_nonzero",
                    "returncode": proc.returncode,
                },
                full={"stderr": tail},
            )
        try:
            parsed = json.loads(stdout.decode("utf-8", errors="replace"))
        except json.JSONDecodeError as e:
            return AnalyzerResult(
                summary={"errorMessage": f"sandbox_invalid_json:{e}"},
                full={"raw": stdout.decode("utf-8", errors="replace")[:2000]},
            )
        if not parsed.get("success", True):
            return AnalyzerResult(
                summary={"errorMessage": parsed.get("errorMessage", "sandbox_reported_failure")},
                full=parsed,
            )
        return AnalyzerResult(summary=parsed.get("summary", {}), full=parsed)
