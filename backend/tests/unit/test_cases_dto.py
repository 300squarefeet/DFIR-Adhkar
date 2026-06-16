"""Phase 3: smoke tests for Case/Task DTO mappers + Pydantic validation."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from adhkar.api.v1.cases import (
    CaseCreate,
    TaskCreate,
    _case_to_dto,
    _task_to_dto,
)
from adhkar.db.models import Case, Task
from pydantic import ValidationError


def _now() -> datetime:
    return datetime.now(tz=UTC)


def test_case_create_default_severity_and_tlp() -> None:
    body = CaseCreate(title="Suspicious login")
    assert body.severity == 2
    assert body.tlp == "amber"
    assert body.pap == "amber"
    assert body.stage == "open"
    assert body.tags == []
    assert body.custom_fields == {}


def test_case_create_rejects_invalid_severity() -> None:
    with pytest.raises(ValidationError):
        CaseCreate(title="x", severity=5)
    with pytest.raises(ValidationError):
        CaseCreate(title="x", severity=0)


def test_case_create_rejects_empty_title() -> None:
    with pytest.raises(ValidationError):
        CaseCreate(title="")


def test_case_create_rejects_invalid_tlp() -> None:
    with pytest.raises(ValidationError):
        CaseCreate(title="x", tlp="black")  # type: ignore[arg-type]


def test_case_dto_mapper_roundtrip() -> None:
    org = uuid4()
    case_id = uuid4()
    now = _now()
    c = Case(
        id=case_id,
        organization_id=org,
        number=42,
        title="Phishing wave",
        description=None,
        severity=3,
        tlp="amber",
        pap="amber",
        status="Open",
        stage="in_progress",
        resolution=None,
        impact_summary=None,
        assignee_id=None,
        start_date=None,
        end_date=None,
        tags=["phish", "high-priority"],
        custom_fields={"ticket": "JIRA-123"},
        flagged=True,
        created_by=None,
        created_at=now,
        updated_at=now,
    )
    dto = _case_to_dto(c)
    assert dto.number == 42
    assert dto.severity == 3
    assert dto.tags == ["phish", "high-priority"]
    assert dto.custom_fields == {"ticket": "JIRA-123"}
    assert dto.flagged is True


def test_task_create_default_status_waiting() -> None:
    body = TaskCreate(title="Pull workstation memory")
    assert body.status == "Waiting"
    assert body.mandatory is False
    assert body.order_index == 0


def test_task_dto_mapper_roundtrip() -> None:
    now = _now()
    t = Task(
        id=uuid4(),
        organization_id=uuid4(),
        case_id=uuid4(),
        title="Quarantine host",
        group="containment",
        description=None,
        status="InProgress",
        assignee_id=None,
        due_date=None,
        order_index=1,
        mandatory=True,
        created_at=now,
        updated_at=now,
    )
    dto = _task_to_dto(t)
    assert dto.title == "Quarantine host"
    assert dto.group == "containment"
    assert dto.status == "InProgress"
    assert dto.mandatory is True
