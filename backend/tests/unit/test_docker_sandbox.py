"""Docker-sandbox analyzer argv-construction tests (no Docker required)."""

from __future__ import annotations

import pytest
from adhkar.analyzers.docker_sandbox import DockerSandboxAnalyzer, DockerSandboxSpec


def _spec() -> DockerSandboxSpec:
    return DockerSandboxSpec(
        name="Test_Sandbox_0_1",
        description="test",
        supported_types=frozenset({"ip"}),
        image="ghcr.io/adhkar/test-analyzer:latest",
        command=("python", "/app/run.py"),
        memory_limit="128m",
        cpus="0.25",
        network="none",
    )


def test_argv_drops_caps_and_disables_network_and_pins_image() -> None:
    a = DockerSandboxAnalyzer(_spec())
    argv = a._docker_argv()  # type: ignore[attr-defined]
    assert argv[0] == "docker"
    assert argv[1] == "run"
    assert "--rm" in argv
    assert "--read-only" in argv
    assert "--cap-drop=ALL" in argv
    assert "--security-opt=no-new-privileges" in argv
    assert "--network=none" in argv
    assert "--memory=128m" in argv
    assert "--cpus=0.25" in argv
    assert "ghcr.io/adhkar/test-analyzer:latest" in argv
    # Command appended after image.
    assert argv[-2:] == ["python", "/app/run.py"]


@pytest.mark.asyncio
async def test_unsupported_datatype_returns_structured_error() -> None:
    a = DockerSandboxAnalyzer(_spec())
    r = await a.run("url", "https://x")
    assert "unsupported_dataType" in r.summary["errorMessage"]


@pytest.mark.asyncio
async def test_missing_docker_cli_returns_structured_error(monkeypatch) -> None:
    # Force PATH lookup miss by pointing image to a docker subcommand we don't override
    bad_spec = DockerSandboxSpec(
        name="x",
        description="",
        supported_types=frozenset({"ip"}),
        image="img",
    )
    a = DockerSandboxAnalyzer(bad_spec)

    async def fake_exec(*args, **kwargs):
        raise FileNotFoundError("docker")

    import asyncio

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    r = await a.run("ip", "1.2.3.4")
    assert r.summary["errorMessage"] == "docker_cli_not_found"
