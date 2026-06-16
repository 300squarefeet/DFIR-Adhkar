"""Jira Cloud responder: create an issue from a case/alert/observable.

Auth is Basic (email + API token) per Jira Cloud docs. Caller passes:
  url: 'https://acme.atlassian.net' (no trailing /rest/api/3)
  email: 'soc@acme'
  api_token: '...'
  project_key: 'SEC'
  issue_type: 'Task' (optional, default 'Task')
  summary: '...' (optional, defaults to the entity ref)
  description: '...' (optional, defaults to a short stub)

We do NOT cache credentials; every invocation receives them in the payload.
For long-running production use, wire these through NotificationEndpoint
config so the secret isn't sent on the wire each call."""

from __future__ import annotations

import base64
from typing import Any

import httpx

from adhkar.responders.base import Responder, ResponderResult


class JiraTicketResponder(Responder):
    name = "jira.ticket.create.v1"
    description = "Create a Jira Cloud issue for the target entity."
    supported_entity_types = frozenset({"case", "alert", "observable"})
    confirm_required = True

    async def run(
        self, entity_type: str, entity_id: str, payload: dict[str, Any]
    ) -> ResponderResult:
        url = str(payload.get("url") or "").rstrip("/")
        email = str(payload.get("email") or "")
        token = str(payload.get("api_token") or "")
        project = str(payload.get("project_key") or "")
        if not (url.startswith("https://") and email and token and project):
            return ResponderResult(
                status="failed",
                summary="missing_required_field",
                details={"required": ["url(https)", "email", "api_token", "project_key"]},
            )
        issue_type = str(payload.get("issue_type") or "Task")
        summary = str(payload.get("summary") or f"{entity_type} {entity_id}")
        description = str(
            payload.get("description")
            or f"Adhkar IR created this ticket for {entity_type} {entity_id}."
        )
        body = {
            "fields": {
                "project": {"key": project},
                "issuetype": {"name": issue_type},
                "summary": summary[:255],
                "description": {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [{"type": "text", "text": description[:32000]}],
                        }
                    ],
                },
            }
        }
        basic = base64.b64encode(f"{email}:{token}".encode()).decode("ascii")
        headers = {
            "Authorization": f"Basic {basic}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(f"{url}/rest/api/3/issue", json=body, headers=headers)
        except httpx.HTTPError as e:
            return ResponderResult(
                status="failed",
                summary=f"http_error:{type(e).__name__}",
                details={"url": url},
            )
        if 200 <= resp.status_code < 300:
            try:
                created = resp.json()
            except ValueError:
                created = {}
            return ResponderResult(
                status="ok",
                summary=f"http_{resp.status_code}",
                details={"key": str(created.get("key", "")), "id": str(created.get("id", ""))},
            )
        return ResponderResult(
            status="failed",
            summary=f"http_{resp.status_code}",
            details={"body": resp.text[:500]},
        )
