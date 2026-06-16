"""Phase 4: smoke tests for Alert DTO + Pydantic validation."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from adhkar.api.v1.alerts import AlertCreate, AlertPatch, _alert_dto
from adhkar.db.models import Alert
from pydantic import ValidationError


def test_alert_create_required_fields() -> None:
    body = AlertCreate(
        type="siem.alert", source="splunk", source_ref="abc-123", title="High CPU on host01"
    )
    assert body.severity == 2
    assert body.tlp == "amber"
    assert body.tags == []


def test_alert_create_rejects_empty_type() -> None:
    with pytest.raises(ValidationError):
        AlertCreate(type="", source="x", source_ref="y", title="t")


def test_alert_patch_partial_update() -> None:
    p = AlertPatch(status="Ignored")
    dumped = p.model_dump(exclude_unset=True)
    assert dumped == {"status": "Ignored"}


def test_alert_patch_rejects_invalid_status() -> None:
    with pytest.raises(ValidationError):
        AlertPatch(status="Unknown")  # type: ignore[arg-type]


def test_alert_dto_mapper() -> None:
    now = datetime.now(tz=UTC)
    a = Alert(
        id=uuid4(),
        organization_id=uuid4(),
        type="siem.alert",
        source="splunk",
        source_ref="abc-123",
        title="High CPU",
        description=None,
        severity=3,
        tlp="amber",
        pap="amber",
        status="New",
        date=None,
        tags=["cpu"],
        custom_fields={"host": "host01"},
        raw_payload=None,
        case_id=None,
        imported_at=None,
        created_by=None,
        created_at=now,
        updated_at=now,
    )
    dto = _alert_dto(a)
    assert dto.type == "siem.alert"
    assert dto.source == "splunk"
    assert dto.source_ref == "abc-123"
    assert dto.tags == ["cpu"]
    assert dto.custom_fields == {"host": "host01"}
