"""Responder framework + WebhookNotifyResponder unit tests."""

from __future__ import annotations

import httpx
import pytest
from adhkar.responders.base import (
    Responder,
    ResponderResult,
    get_responder_registry,
)
from adhkar.responders.webhook_notify import WebhookNotifyResponder


class _DummyResponder(Responder):
    name = "dummy.v1"
    description = "no-op"
    supported_entity_types = frozenset({"case"})
    confirm_required = True

    async def run(self, entity_type, entity_id, payload):
        return ResponderResult(status="ok", summary="dummy_ran", details={"id": entity_id})


@pytest.mark.asyncio
async def test_registry_register_and_lookup() -> None:
    reg = get_responder_registry()
    reg.register(_DummyResponder())
    found = reg.get("dummy.v1")
    assert found is not None
    assert found.confirm_required is True
    assert found.supported_entity_types == frozenset({"case"})
    assert any(r.name == "dummy.v1" for r in reg.all())


@pytest.mark.asyncio
async def test_webhook_notify_rejects_invalid_url() -> None:
    r = WebhookNotifyResponder()
    res = await r.run("case", "c1", {"url": "javascript:alert(1)"})
    assert res.status == "failed"
    assert res.summary == "missing_or_invalid_url"


@pytest.mark.asyncio
async def test_webhook_notify_returns_ok_on_2xx(monkeypatch) -> None:
    async def fake_post(self, url, json, headers):
        return httpx.Response(202, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    r = WebhookNotifyResponder()
    res = await r.run("case", "c1", {"url": "https://hooks.example/x", "message": "hi"})
    assert res.status == "ok"
    assert res.summary == "http_202"


@pytest.mark.asyncio
async def test_webhook_notify_returns_failed_on_5xx(monkeypatch) -> None:
    async def fake_post(self, url, json, headers):
        return httpx.Response(500, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    r = WebhookNotifyResponder()
    res = await r.run("alert", "a1", {"url": "https://hooks.example/x"})
    assert res.status == "failed"
    assert res.summary == "http_500"


@pytest.mark.asyncio
async def test_webhook_notify_handles_network_error(monkeypatch) -> None:
    async def fake_post(self, url, json, headers):
        raise httpx.ConnectError("no route")

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    r = WebhookNotifyResponder()
    res = await r.run("case", "c1", {"url": "https://x.invalid"})
    assert res.status == "failed"
    assert "ConnectError" in res.summary
