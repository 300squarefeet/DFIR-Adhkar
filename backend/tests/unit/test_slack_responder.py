"""Slack notify responder unit tests."""

from __future__ import annotations

import httpx
import pytest
from adhkar.responders.slack_notify import SlackNotifyResponder


@pytest.mark.asyncio
async def test_slack_rejects_invalid_url() -> None:
    r = SlackNotifyResponder()
    res = await r.run("case", "c1", {"url": "ftp://nope"})
    assert res.status == "failed"
    assert res.summary == "missing_or_invalid_url"


@pytest.mark.asyncio
async def test_slack_posts_envelope(monkeypatch) -> None:
    captured: dict[str, object] = {}

    async def fake_post(self, url, json):
        captured["url"] = url
        captured["json"] = json
        return httpx.Response(200, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    r = SlackNotifyResponder()
    res = await r.run("case", "c-123", {"url": "https://hooks.slack/x", "message": "hello"})
    assert res.status == "ok"
    assert res.summary == "http_200"
    body = captured["json"]
    assert isinstance(body, dict)
    assert body["text"] == "hello"
    assert body["attachments"][0]["fields"][0]["value"] == "case:c-123"


@pytest.mark.asyncio
async def test_slack_handles_5xx(monkeypatch) -> None:
    async def fake_post(self, url, json):
        return httpx.Response(503, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    r = SlackNotifyResponder()
    res = await r.run("alert", "a1", {"url": "https://hooks.slack/x"})
    assert res.status == "failed"
    assert res.summary == "http_503"
