"""Audit + outbox emit helper.

Single function to call from any mutation endpoint: writes an AuditLog
row AND an OutboxEvent row in the same transaction. The outbox worker
(adhkar.workers.outbox_publisher) then publishes the event to Redis
pub/sub for live-feed subscribers.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from adhkar.db.models import AuditLog, OutboxEvent


async def audit_and_emit(
    db: AsyncSession,
    *,
    actor_user_id: UUID | None,
    organization_id: UUID | None,
    action: str,
    entity_type: str,
    entity_id: UUID | None,
    diff: dict[str, Any] | None = None,
    request_id: str | None = None,
    ip: str | None = None,
    event_type: str | None = None,
    payload: dict[str, Any] | None = None,
    emit_outbox: bool = True,
) -> tuple[AuditLog, OutboxEvent | None]:
    """Insert AuditLog + OutboxEvent in the current transaction.

    The default `event_type` is `{entity_type}.{action}` (e.g. `user.created`).
    The default outbox payload is the audit diff + entity_id.
    """
    diff = diff or {}
    audit = AuditLog(
        actor_user_id=actor_user_id,
        organization_id=organization_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        diff=diff,
        request_id=request_id,
        ip=ip,
    )
    db.add(audit)
    event_payload = payload or {
        "entity_id": str(entity_id) if entity_id else None,
        "diff": diff,
    }
    if emit_outbox:
        outbox: OutboxEvent | None = OutboxEvent(
            organization_id=organization_id,
            event_type=event_type or f"{entity_type}.{action}",
            payload=event_payload,
        )
        db.add(outbox)
    else:
        outbox = None
    await db.flush()
    return audit, outbox
