"""Jira ticket responder unit tests."""

from __future__ import annotations

import httpx
import pytest
from adhkar.responders.jira_ticket import JiraTicketResponder


@pytest.mark.asyncio
async def test_jira_rejects_missing_required_fields() -> None:
    r = JiraTicketResponder()
    res = await r.run("case", "c1", {"url": "https://acme.atlassian.net"})
    assert res.status == "failed"
    assert res.summary == "missing_required_field"


@pytest.mark.asyncio
async def test_jira_rejects_non_https_url() -> None:
    r = JiraTicketResponder()
    res = await r.run(
        "case",
        "c1",
        {
            "url": "http://insecure.jira",
            "email": "x@y",
            "api_token": "tok",
            "project_key": "SEC",
        },
    )
    assert res.status == "failed"
    assert res.summary == "missing_required_field"


@pytest.mark.asyncio
async def test_jira_creates_issue(monkeypatch) -> None:
    captured: dict[str, object] = {}

    async def fake_post(self, url, json, headers):
        captured["url"] = url
        captured["json"] = json
        captured["auth"] = headers["Authorization"]
        return httpx.Response(
            201,
            json={"key": "SEC-123", "id": "10456"},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    r = JiraTicketResponder()
    res = await r.run(
        "case",
        "abc",
        {
            "url": "https://acme.atlassian.net",
            "email": "soc@acme",
            "api_token": "tok",
            "project_key": "SEC",
            "summary": "Phishing wave",
        },
    )
    assert res.status == "ok"
    assert res.summary == "http_201"
    assert res.details["key"] == "SEC-123"
    assert captured["url"] == "https://acme.atlassian.net/rest/api/3/issue"
    body = captured["json"]
    assert isinstance(body, dict)
    assert body["fields"]["project"]["key"] == "SEC"
    assert body["fields"]["summary"] == "Phishing wave"
    assert str(captured["auth"]).startswith("Basic ")


@pytest.mark.asyncio
async def test_jira_handles_4xx_with_body(monkeypatch) -> None:
    async def fake_post(self, url, json, headers):
        return httpx.Response(
            400,
            text="bad",
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    r = JiraTicketResponder()
    res = await r.run(
        "alert",
        "a",
        {
            "url": "https://acme.atlassian.net",
            "email": "x",
            "api_token": "y",
            "project_key": "K",
        },
    )
    assert res.status == "failed"
    assert res.summary == "http_400"
    assert res.details["body"] == "bad"
