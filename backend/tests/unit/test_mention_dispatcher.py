"""Verify emit_mentions resolves @-tokens and emits one audit event per match."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from adhkar.services import mentions as m


def _users(*display_names: str) -> list[SimpleNamespace]:
    return [SimpleNamespace(id=uuid4(), display_name=n) for n in display_names]


def _mock_db_returning(users: list[SimpleNamespace]) -> MagicMock:
    db = MagicMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = users
    db.execute = AsyncMock(return_value=result)
    return db


@pytest.mark.asyncio
async def test_no_at_token_no_dispatch(monkeypatch):
    audit = AsyncMock()
    monkeypatch.setattr(m, "audit_and_emit", audit)
    db = _mock_db_returning([])
    n = await m.emit_mentions(
        db,
        org_id=uuid4(),
        actor_user_id=uuid4(),
        content="plain text, no mention",
        extra_diff={"case_id": "x"},
    )
    assert n == 0
    audit.assert_not_called()
    db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_one_match_one_dispatch(monkeypatch):
    audit = AsyncMock()
    monkeypatch.setattr(m, "audit_and_emit", audit)
    users = _users("alice")
    db = _mock_db_returning(users)
    org_id = uuid4()
    actor = uuid4()
    n = await m.emit_mentions(
        db,
        org_id=org_id,
        actor_user_id=actor,
        content="ping @alice please",
        extra_diff={"case_id": "C-1"},
    )
    assert n == 1
    assert audit.await_count == 1
    kwargs = audit.await_args.kwargs
    assert kwargs["action"] == "mentioned"
    assert kwargs["entity_type"] == "user"
    assert kwargs["entity_id"] == users[0].id
    assert kwargs["organization_id"] == org_id
    assert kwargs["actor_user_id"] == actor
    assert kwargs["diff"]["case_id"] == "C-1"
    assert kwargs["diff"]["mentioned_display_name"] == "alice"


@pytest.mark.asyncio
async def test_multiple_matches_one_event_each(monkeypatch):
    audit = AsyncMock()
    monkeypatch.setattr(m, "audit_and_emit", audit)
    users = _users("alice", "bob")
    db = _mock_db_returning(users)
    n = await m.emit_mentions(
        db,
        org_id=uuid4(),
        actor_user_id=uuid4(),
        content="cc @alice and @bob",
        extra_diff={"case_id": "C-2"},
    )
    assert n == 2
    assert audit.await_count == 2
    seen = {call.kwargs["entity_id"] for call in audit.await_args_list}
    assert seen == {u.id for u in users}


@pytest.mark.asyncio
async def test_self_mention_is_silent(monkeypatch):
    audit = AsyncMock()
    monkeypatch.setattr(m, "audit_and_emit", audit)
    actor = uuid4()
    me = SimpleNamespace(id=actor, display_name="me")
    db = _mock_db_returning([me])
    n = await m.emit_mentions(
        db,
        org_id=uuid4(),
        actor_user_id=actor,
        content="@me note to self",
        extra_diff={"case_id": "C-self"},
    )
    assert n == 0
    audit.assert_not_called()


@pytest.mark.asyncio
async def test_extra_diff_passthrough(monkeypatch):
    audit = AsyncMock()
    monkeypatch.setattr(m, "audit_and_emit", audit)
    db = _mock_db_returning(_users("carol"))
    await m.emit_mentions(
        db,
        org_id=uuid4(),
        actor_user_id=uuid4(),
        content="@carol fyi",
        extra_diff={"task_id": "T-9", "case_id": "C-3", "task_log_id": "L-1"},
    )
    diff = audit.await_args.kwargs["diff"]
    assert diff["task_id"] == "T-9"
    assert diff["case_id"] == "C-3"
    assert diff["task_log_id"] == "L-1"
    assert diff["mentioned_display_name"] == "carol"
