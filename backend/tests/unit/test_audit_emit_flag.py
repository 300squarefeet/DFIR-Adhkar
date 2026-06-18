"""audit_and_emit(emit_outbox=False) writes AuditLog without OutboxEvent.

Uses a MagicMock AsyncSession (no real database) because AuditLog and
OutboxEvent use Postgres-specific dialect types (INET, JSONB, PgUUID)
that can't round-trip through SQLite. We assert by inspecting what
db.add() received."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from adhkar.audit import audit_and_emit
from adhkar.db.models import AuditLog, OutboxEvent


def _mock_session() -> MagicMock:
    sess = MagicMock()
    sess.add = MagicMock()
    sess.flush = AsyncMock()
    return sess


@pytest.mark.asyncio
async def test_default_writes_audit_and_outbox() -> None:
    db = _mock_session()
    audit, outbox = await audit_and_emit(
        db,
        actor_user_id=None,
        organization_id=None,
        action="touched",
        entity_type="case",
        entity_id=uuid4(),
        diff={"k": "v"},
    )
    assert isinstance(audit, AuditLog)
    assert isinstance(outbox, OutboxEvent)
    added_types = [type(call.args[0]).__name__ for call in db.add.call_args_list]
    assert "AuditLog" in added_types
    assert "OutboxEvent" in added_types
    assert db.flush.await_count == 1


@pytest.mark.asyncio
async def test_emit_outbox_false_skips_outbox() -> None:
    db = _mock_session()
    audit, outbox = await audit_and_emit(
        db,
        actor_user_id=None,
        organization_id=None,
        action="rejected",
        entity_type="user",
        entity_id=None,
        diff={"why": "tampered"},
        emit_outbox=False,
    )
    assert isinstance(audit, AuditLog)
    assert outbox is None
    added_types = [type(call.args[0]).__name__ for call in db.add.call_args_list]
    assert "AuditLog" in added_types
    assert "OutboxEvent" not in added_types
    assert db.flush.await_count == 1
