"""source_ip extracts the real client IP from a FastAPI Request."""

from __future__ import annotations

from typing import Any

import pytest
from starlette.datastructures import Headers


class _StubClient:
    def __init__(self, host: str) -> None:
        self.host = host


class _StubRequest:
    """Minimal duck-type stand-in for fastapi.Request."""

    def __init__(self, headers: dict[str, str], client_host: str | None) -> None:
        self.headers = Headers(headers)
        self.client = _StubClient(client_host) if client_host else None


def _r(headers: dict[str, str] | None = None, client_host: str | None = "127.0.0.1") -> Any:
    return _StubRequest(headers or {}, client_host)


@pytest.fixture
def source_ip_fn():
    from adhkar.core.source_ip import source_ip

    return source_ip


def test_returns_left_most_xff_when_present(source_ip_fn) -> None:
    req = _r({"x-forwarded-for": "203.0.113.42, 10.0.0.1, 10.0.0.2"})
    assert source_ip_fn(req) == "203.0.113.42"


def test_skips_private_xff_entries(source_ip_fn) -> None:
    req = _r({"x-forwarded-for": "10.0.0.1, 192.168.1.5, 203.0.113.42"})
    assert source_ip_fn(req) == "203.0.113.42"


def test_falls_back_to_x_real_ip_when_no_xff(source_ip_fn) -> None:
    req = _r({"x-real-ip": "198.51.100.7"})
    assert source_ip_fn(req) == "198.51.100.7"


def test_falls_back_to_client_host_when_no_headers(source_ip_fn) -> None:
    req = _r({}, client_host="192.0.2.1")
    assert source_ip_fn(req) == "192.0.2.1"


def test_returns_none_when_no_signal(source_ip_fn) -> None:
    req = _r({}, client_host=None)
    assert source_ip_fn(req) is None


def test_treats_malformed_xff_entries_as_private_and_skips(source_ip_fn) -> None:
    req = _r({"x-forwarded-for": "not-an-ip, 203.0.113.42"})
    assert source_ip_fn(req) == "203.0.113.42"


def test_loopback_xff_entries_are_skipped(source_ip_fn) -> None:
    req = _r({"x-forwarded-for": "127.0.0.1, 203.0.113.42"})
    assert source_ip_fn(req) == "203.0.113.42"
