"""Slack/Mattermost/Teams incoming-webhook responder.

Formats the payload as a Slack-style {text, attachments} envelope which is
the lowest common denominator across Slack, Mattermost, and Teams
incoming-webhook implementations."""

from __future__ import annotations

from typing import Any

import httpx

from adhkar.responders.base import Responder, ResponderResult


class SlackNotifyResponder(Responder):
    name = "slack.notify.v1"
    description = "Post a message to Slack/Mattermost/Teams via an incoming webhook."
    supported_entity_types = frozenset({"case", "alert", "observable"})
    confirm_required = False

    async def run(
        self, entity_type: str, entity_id: str, payload: dict[str, Any]
    ) -> ResponderResult:
        url = str(payload.get("url") or "")
        if not url.startswith(("http://", "https://")):
            return ResponderResult(
                status="failed",
                summary="missing_or_invalid_url",
                details={"url": url},
            )
        message = str(payload.get("message") or f"{entity_type} {entity_id} flagged.")
        slack_body: dict[str, Any] = {
            "text": message,
            "attachments": [
                {
                    "fallback": message,
                    "color": "#F59E0B",
                    "fields": [
                        {"title": "Entity", "value": f"{entity_type}:{entity_id}", "short": True},
                    ],
                }
            ],
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json=slack_body)
        except httpx.HTTPError as e:
            return ResponderResult(
                status="failed",
                summary=f"http_error:{type(e).__name__}",
                details={"url": url},
            )
        ok = 200 <= resp.status_code < 300
        return ResponderResult(
            status="ok" if ok else "failed",
            summary=f"http_{resp.status_code}",
            details={"url": url},
        )
