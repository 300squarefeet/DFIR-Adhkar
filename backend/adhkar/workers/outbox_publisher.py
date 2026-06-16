"""Outbox publisher: poll outbox_events, publish to Redis pub/sub, mark published_at."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime

import redis.asyncio as redis_async
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from adhkar.core.settings import Settings
from adhkar.db.engine import create_engine
from adhkar.db.models import OutboxEvent

_log = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 0.5
BATCH_SIZE = 100


def _channel(org_id: str | None) -> str:
    return f"adhkar.events.{org_id}" if org_id else "adhkar.events.global"


async def _publish_pending(settings: Settings, redis: redis_async.Redis) -> int:  # type: ignore[type-arg]
    engine = create_engine(settings)
    sf = async_sessionmaker(engine, expire_on_commit=False)
    published = 0
    try:
        async with sf() as session, session.begin():
            rows = (
                (
                    await session.execute(
                        select(OutboxEvent)
                        .where(OutboxEvent.published_at.is_(None))
                        .order_by(OutboxEvent.created_at)
                        .limit(BATCH_SIZE)
                    )
                )
                .scalars()
                .all()
            )
            now = datetime.now(tz=UTC)
            for ev in rows:
                msg = json.dumps(
                    {
                        "id": str(ev.id),
                        "organization_id": str(ev.organization_id) if ev.organization_id else None,
                        "event_type": ev.event_type,
                        "payload": ev.payload,
                        "created_at": ev.created_at.isoformat(),
                    }
                )
                await redis.publish(
                    _channel(str(ev.organization_id) if ev.organization_id else None), msg
                )
                ev.published_at = now
                published += 1
    finally:
        await engine.dispose()
    return published


async def run_outbox_publisher(settings: Settings) -> None:
    """Long-running loop: poll outbox + publish to Redis. Stops on cancellation."""
    redis = redis_async.from_url(settings.redis_url, decode_responses=True)
    try:
        while True:
            try:
                count = await _publish_pending(settings, redis)
                if count > 0:
                    _log.debug("outbox.publish count=%d", count)
            except asyncio.CancelledError:
                raise
            except Exception:
                _log.exception("outbox publisher iteration failed")
            await asyncio.sleep(POLL_INTERVAL_SECONDS)
    finally:
        await redis.close()
