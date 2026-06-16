"""Webhook responder: POST JSON to a configured URL.

Useful as the universal escape hatch (Slack/Teams/Mattermost/PagerDuty all
accept incoming webhooks). The actual destination URL comes from the
payload, so this responder is configured per-invocation."""

from __future__ import annotations

from typing import Any

import httpx

from adhkar.responders.base import Responder, ResponderResult


class WebhookNotifyResponder(Responder):
    name = "webhook.notify.v1"
    description = "POST a JSON payload to an external webhook URL."
    supported_entity_types = frozenset({"case", "alert", "observable", "task"})
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
        body = payload.get("body") or {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "message": payload.get("message", ""),
        }
        headers = {k: str(v) for k, v in (payload.get("headers") or {}).items()}
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json=body, headers=headers)
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
