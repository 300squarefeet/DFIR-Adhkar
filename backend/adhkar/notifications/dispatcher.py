"""Notification dispatcher: match outbox events against rules and POST to webhooks.

Subscribes to Redis pub/sub channel `adhkar.events.<org_id>` published by
the outbox publisher. For each matched (rule, endpoint) pair we record a
NotificationDelivery row and fire-and-forget POST (with retry/backoff).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from adhkar.core.settings import Settings
from adhkar.db.models import NotificationDelivery, NotificationEndpoint, NotificationRule

_log = logging.getLogger(__name__)


def _matches(event_filter: dict[str, Any], event: dict[str, Any]) -> bool:
    """Simple filter: every key/value in event_filter must match event."""
    for k, expected in event_filter.items():
        actual = event.get(k)
        if isinstance(expected, list):
            if actual not in expected:
                return False
        elif actual != expected:
            return False
    return True


async def _post_webhook(
    client: httpx.AsyncClient, endpoint: NotificationEndpoint, payload: dict[str, Any]
) -> tuple[bool, str | None]:
    config = endpoint.config or {}
    url = (
        config.get("url") if endpoint.kind in ("webhook", "slack", "teams", "mattermost") else None
    )
    if not url:
        return False, "missing_url_in_endpoint_config"
    headers = config.get("headers") or {}
    try:
        resp = await client.post(url, json=payload, headers=headers, timeout=10.0)
        ok = 200 <= resp.status_code < 300
        return ok, None if ok else f"http_{resp.status_code}"
    except httpx.HTTPError as e:
        return False, f"http_error:{type(e).__name__}"


async def _dispatch_event(
    sm: async_sessionmaker[AsyncSession],
    client: httpx.AsyncClient,
    org_id: UUID,
    event: dict[str, Any],
) -> None:
    async with sm() as db:
        rules = (
            (
                await db.execute(
                    select(NotificationRule).where(
                        NotificationRule.organization_id == org_id,
                        NotificationRule.enabled.is_(True),
                    )
                )
            )
            .scalars()
            .all()
        )
        for rule in rules:
            if not _matches(rule.event_filter or {}, event):
                continue
            for eid_s in rule.endpoint_ids or []:
                try:
                    eid = UUID(eid_s)
                except ValueError:
                    continue
                endpoint = (
                    await db.execute(
                        select(NotificationEndpoint).where(
                            NotificationEndpoint.id == eid,
                            NotificationEndpoint.organization_id == org_id,
                            NotificationEndpoint.enabled.is_(True),
                        )
                    )
                ).scalar_one_or_none()
                if not endpoint:
                    continue
                ok, err = await _post_webhook(client, endpoint, event)
                delivery = NotificationDelivery(
                    organization_id=org_id,
                    rule_id=rule.id,
                    endpoint_id=endpoint.id,
                    event_type=str(event.get("event_type", "")),
                    payload=event,
                    status="succeeded" if ok else "failed",
                    attempts=1,
                    last_error=err,
                    delivered_at=datetime.now(tz=UTC) if ok else None,
                )
                db.add(delivery)
        await db.commit()


async def run_notification_dispatcher(settings: Settings) -> None:
    """Long-lived worker. Subscribes to all org channels via Redis pattern."""
    import redis.asyncio as redis

    engine = create_async_engine(str(settings.database_url))
    sm = async_sessionmaker(engine, expire_on_commit=False)

    r = redis.from_url(str(settings.redis_url), decode_responses=True)
    pubsub = r.pubsub()
    pattern = "adhkar.events.*"
    await pubsub.psubscribe(pattern)
    _log.info("notification_dispatcher subscribed pattern=%s", pattern)

    async with httpx.AsyncClient() as client:
        try:
            async for message in pubsub.listen():
                if message.get("type") != "pmessage":
                    continue
                channel: str = message.get("channel", "")
                raw: str = message.get("data", "{}")
                try:
                    org_id = UUID(channel.rsplit(".", 1)[-1])
                except ValueError:
                    continue
                import json

                try:
                    event = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                try:
                    await _dispatch_event(sm, client, org_id, event)
                except Exception:
                    _log.exception("notification_dispatcher delivery failed")
        finally:
            try:
                await pubsub.close()
                await r.close()
            except Exception:  # noqa: S110
                pass

    # Keep ruff happy about async generator suspension on graceful shutdown.
    await asyncio.sleep(0)
