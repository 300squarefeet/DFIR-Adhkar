"""Alert ingestion + promotion endpoints (Phase 4)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from adhkar.api.deps import (
    CurrentUser,
    get_db,
    require_current_org,
    require_permission,
)
from adhkar.audit import audit_and_emit
from adhkar.db.models import Alert, Case
from adhkar.db.repositories.cases import CaseRepository

router = APIRouter(prefix="/v1/alerts", tags=["alerts"])

TLP = Literal["white", "green", "amber", "amber-strict", "red"]
PAP = Literal["white", "green", "amber", "red"]
STATUS = Literal["New", "Updated", "Ignored", "Imported"]


class AlertDTO(BaseModel):
    id: UUID
    organization_id: UUID
    type: str
    source: str
    source_ref: str
    title: str
    description: str | None
    severity: int
    tlp: str
    pap: str
    status: str
    date: datetime | None
    tags: list[str]
    custom_fields: dict[str, Any]
    case_id: UUID | None
    imported_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AlertCreate(BaseModel):
    type: str = Field(min_length=1, max_length=100)
    source: str = Field(min_length=1, max_length=100)
    source_ref: str = Field(min_length=1, max_length=255)
    title: str = Field(min_length=1, max_length=500)
    description: str | None = None
    severity: int = Field(default=2, ge=1, le=4)
    tlp: TLP = "amber"
    pap: PAP = "amber"
    date: datetime | None = None
    tags: list[str] = []
    custom_fields: dict[str, Any] = {}
    raw_payload: dict[str, Any] | None = None


class AlertPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = None
    severity: int | None = Field(default=None, ge=1, le=4)
    tlp: TLP | None = None
    pap: PAP | None = None
    status: STATUS | None = None
    tags: list[str] | None = None
    custom_fields: dict[str, Any] | None = None


class PromotePayload(BaseModel):
    case_title: str | None = None
    case_severity: int | None = Field(default=None, ge=1, le=4)


def _alert_dto(a: Alert) -> AlertDTO:
    return AlertDTO(
        id=a.id,
        organization_id=a.organization_id,
        type=a.type,
        source=a.source,
        source_ref=a.source_ref,
        title=a.title,
        description=a.description,
        severity=a.severity,
        tlp=a.tlp,
        pap=a.pap,
        status=a.status,
        date=a.date,
        tags=list(a.tags),
        custom_fields=dict(a.custom_fields),
        case_id=a.case_id,
        imported_at=a.imported_at,
        created_at=a.created_at,
        updated_at=a.updated_at,
    )


@router.get(
    "/export-csv",
    response_class=PlainTextResponse,
    responses={200: {"content": {"text/csv": {}}}},
)
async def export_alerts_csv(
    _user: Annotated[CurrentUser, Depends(require_permission("viewAlert"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
    alert_status: STATUS | None = None,
    source: str | None = None,
    severity: int | None = None,
    tag: str | None = None,
    unpromoted: bool | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    updated_since: datetime | None = None,
) -> PlainTextResponse:
    """CSV dump of alerts. Same filter surface as the list endpoint
    (including RC174 updated_since)."""
    import csv
    import io

    stmt = select(Alert).where(Alert.organization_id == org_id)
    if alert_status:
        stmt = stmt.where(Alert.status == alert_status)
    if source:
        stmt = stmt.where(Alert.source == source)
    if severity is not None:
        stmt = stmt.where(Alert.severity == severity)
    if tag:
        stmt = stmt.where(Alert.tags.contains([tag]))
    if unpromoted is True:
        stmt = stmt.where(Alert.case_id.is_(None))
    elif unpromoted is False:
        stmt = stmt.where(Alert.case_id.is_not(None))
    if since is not None:
        stmt = stmt.where(Alert.created_at >= since)
    if until is not None:
        stmt = stmt.where(Alert.created_at < until)
    if updated_since is not None:
        stmt = stmt.where(Alert.updated_at >= updated_since)
    rows = (await db.execute(stmt.order_by(Alert.created_at.desc()))).scalars().all()
    buf = io.StringIO()
    w = csv.writer(buf, quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
    w.writerow(
        [
            "type",
            "source",
            "source_ref",
            "title",
            "severity",
            "tlp",
            "status",
            "case_id",
            "tags",
            "created_at",
        ]
    )
    for a in rows:
        w.writerow(
            [
                a.type,
                a.source,
                a.source_ref,
                a.title,
                a.severity,
                a.tlp,
                a.status,
                str(a.case_id) if a.case_id else "",
                ",".join(a.tags),
                a.created_at.isoformat(),
            ]
        )
    return PlainTextResponse(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="adhkar-alerts.csv"'},
    )


@router.get("/recent", response_model=list[AlertDTO])
async def list_recent_alerts(
    _user: Annotated[CurrentUser, Depends(require_permission("viewAlert"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 10,
    unpromoted: bool | None = None,
    source: str | None = None,
    tag: str | None = None,
    severity_gte: int | None = None,
) -> list[AlertDTO]:
    """N most-recently-updated alerts (`updated_at` DESC) for the current
    org, default 10, cap 50. Optional `unpromoted=true` to filter to
    alerts not yet promoted to a case (`case_id IS NULL`). Optional
    `source=<name>` exact-match filter to scope to one ingestion source
    (case-insensitive). Optional `tag=<name>` exact-match (ARRAY.contains).
    Optional `severity_gte=N` keeps only alerts at or above that severity
    (1..4). Same DTO shape as the list endpoint."""
    safe_limit = max(1, min(50, int(limit)))
    stmt = (
        select(Alert)
        .where(Alert.organization_id == org_id)
        .order_by(Alert.updated_at.desc())
        .limit(safe_limit)
    )
    if unpromoted is True:
        stmt = stmt.where(Alert.case_id.is_(None))
    elif unpromoted is False:
        stmt = stmt.where(Alert.case_id.is_not(None))
    if source is not None:
        stmt = stmt.where(func.lower(Alert.source) == source.lower())
    if tag is not None:
        stmt = stmt.where(Alert.tags.contains([tag]))
    if severity_gte is not None:
        stmt = stmt.where(Alert.severity >= max(1, min(4, severity_gte)))
    rows = (await db.execute(stmt)).scalars().all()
    return [_alert_dto(a) for a in rows]


@router.get("", response_model=list[AlertDTO])
async def list_alerts(
    _user: Annotated[CurrentUser, Depends(require_permission("viewAlert"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
    alert_status: STATUS | None = None,
    source: str | None = None,
    severity: int | None = None,
    tag: str | None = None,
    unpromoted: bool | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    updated_since: datetime | None = None,
    limit: int = 100,
) -> list[AlertDTO]:
    """Alert list. `since`/`until` bound created_at; `updated_since=<ISO>`
    is a delta-sync companion that bounds updated_at and switches the
    sort to updated_at DESC so polling cursors land on the latest edits."""
    stmt = select(Alert).where(Alert.organization_id == org_id)
    if alert_status:
        stmt = stmt.where(Alert.status == alert_status)
    if source:
        stmt = stmt.where(Alert.source == source)
    if severity is not None:
        stmt = stmt.where(Alert.severity == severity)
    if tag:
        stmt = stmt.where(Alert.tags.contains([tag]))
    if unpromoted is True:
        stmt = stmt.where(Alert.case_id.is_(None))
    elif unpromoted is False:
        stmt = stmt.where(Alert.case_id.is_not(None))
    if since is not None:
        stmt = stmt.where(Alert.created_at >= since)
    if until is not None:
        stmt = stmt.where(Alert.created_at < until)
    if updated_since is not None:
        stmt = stmt.where(Alert.updated_at >= updated_since).order_by(Alert.updated_at.desc())
    else:
        stmt = stmt.order_by(Alert.created_at.desc())
    stmt = stmt.limit(limit)
    rows = (await db.execute(stmt)).scalars().all()
    return [_alert_dto(a) for a in rows]


@router.get("/{alert_id}/similar", response_model=list[AlertDTO])
async def list_similar_alerts(
    alert_id: UUID,
    _user: Annotated[CurrentUser, Depends(require_permission("viewAlert"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 50,
) -> list[AlertDTO]:
    """Alerts in the current org sharing (source, source_ref) with this one,
    excluding the source alert itself. Useful when a SIEM re-fires or when
    cross-referencing investigations. Ordered by created_at DESC, cap 200."""
    safe_limit = max(1, min(200, int(limit)))
    src = (
        await db.execute(select(Alert).where(Alert.id == alert_id, Alert.organization_id == org_id))
    ).scalar_one_or_none()
    if src is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "alert_not_found")
    rows = (
        (
            await db.execute(
                select(Alert)
                .where(
                    Alert.organization_id == org_id,
                    Alert.source == src.source,
                    Alert.source_ref == src.source_ref,
                    Alert.id != alert_id,
                )
                .order_by(Alert.created_at.desc())
                .limit(safe_limit)
            )
        )
        .scalars()
        .all()
    )
    return [_alert_dto(a) for a in rows]


class BulkAlertPatch(BaseModel):
    ids: list[UUID] = Field(min_length=1, max_length=200)
    patch: AlertPatch


class BulkAlertResult(BaseModel):
    updated: int
    ids: list[UUID]


@router.post("/bulk-patch", response_model=BulkAlertResult)
async def bulk_patch_alerts(
    body: BulkAlertPatch,
    user: Annotated[CurrentUser, Depends(require_permission("manageAlert"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> BulkAlertResult:
    """Apply the same AlertPatch to up to 200 alerts. Rows outside the
    caller's org are silently dropped. Emits one audit row per id."""
    patch = body.patch.model_dump(exclude_unset=True)
    if not patch:
        return BulkAlertResult(updated=0, ids=[])
    rows = (
        (
            await db.execute(
                select(Alert).where(
                    Alert.organization_id == org_id,
                    Alert.id.in_(body.ids),
                )
            )
        )
        .scalars()
        .all()
    )
    updated_ids: list[UUID] = []
    for a in rows:
        for field, value in patch.items():
            setattr(a, field, value)
        updated_ids.append(a.id)
    await db.flush()
    for aid in updated_ids:
        await audit_and_emit(
            db,
            actor_user_id=user.user_id,
            organization_id=org_id,
            action="bulk_updated",
            entity_type="alert",
            entity_id=aid,
            diff={k: str(v) for k, v in patch.items()},
        )
    return BulkAlertResult(updated=len(updated_ids), ids=updated_ids)


@router.post("", response_model=AlertDTO, status_code=status.HTTP_201_CREATED)
async def ingest_alert(
    body: AlertCreate,
    user: Annotated[CurrentUser, Depends(require_permission("manageAlert"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AlertDTO:
    """Upsert by (org, type, source, source_ref) — dedup. Existing alert is
    updated and its status flips to "Updated"."""
    existing = (
        await db.execute(
            select(Alert).where(
                Alert.organization_id == org_id,
                Alert.type == body.type,
                Alert.source == body.source,
                Alert.source_ref == body.source_ref,
            )
        )
    ).scalar_one_or_none()
    if existing:
        existing.title = body.title
        if body.description is not None:
            existing.description = body.description
        existing.severity = body.severity
        existing.tlp = body.tlp
        existing.pap = body.pap
        existing.tags = body.tags
        existing.custom_fields = body.custom_fields
        if body.raw_payload is not None:
            existing.raw_payload = body.raw_payload
        if existing.status in ("New", "Updated"):
            existing.status = "Updated"
        await db.flush()
        return _alert_dto(existing)
    alert = Alert(
        organization_id=org_id,
        type=body.type,
        source=body.source,
        source_ref=body.source_ref,
        title=body.title,
        description=body.description,
        severity=body.severity,
        tlp=body.tlp,
        pap=body.pap,
        status="New",
        date=body.date,
        tags=body.tags,
        custom_fields=body.custom_fields,
        raw_payload=body.raw_payload,
        created_by=user.user_id,
    )
    db.add(alert)
    await db.flush()
    await audit_and_emit(
        db,
        actor_user_id=user.user_id,
        organization_id=org_id,
        action="ingested",
        entity_type="alert",
        entity_id=alert.id,
        diff={"source": alert.source, "source_ref": alert.source_ref, "title": alert.title},
    )
    return _alert_dto(alert)


@router.get("/{alert_id}", response_model=AlertDTO)
async def get_alert(
    alert_id: UUID,
    _user: Annotated[CurrentUser, Depends(require_permission("viewAlert"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AlertDTO:
    a = (
        await db.execute(select(Alert).where(Alert.id == alert_id, Alert.organization_id == org_id))
    ).scalar_one_or_none()
    if not a:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "alert_not_found")
    return _alert_dto(a)


@router.patch("/{alert_id}", response_model=AlertDTO)
async def patch_alert(
    alert_id: UUID,
    body: AlertPatch,
    _user: Annotated[CurrentUser, Depends(require_permission("manageAlert"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AlertDTO:
    a = (
        await db.execute(select(Alert).where(Alert.id == alert_id, Alert.organization_id == org_id))
    ).scalar_one_or_none()
    if not a:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "alert_not_found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(a, field, value)
    await db.flush()
    return _alert_dto(a)


@router.delete("/{alert_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_alert(
    alert_id: UUID,
    _user: Annotated[CurrentUser, Depends(require_permission("manageAlert"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    a = (
        await db.execute(select(Alert).where(Alert.id == alert_id, Alert.organization_id == org_id))
    ).scalar_one_or_none()
    if not a:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "alert_not_found")
    await db.delete(a)
    await db.flush()


@router.post("/{alert_id}/promote", status_code=status.HTTP_201_CREATED)
async def promote_alert(
    alert_id: UUID,
    body: PromotePayload,
    user: Annotated[CurrentUser, Depends(require_permission("manageCase"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    a = (
        await db.execute(select(Alert).where(Alert.id == alert_id, Alert.organization_id == org_id))
    ).scalar_one_or_none()
    if not a:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "alert_not_found")
    if a.case_id is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "alert_already_promoted")
    repo = CaseRepository(db, org_id)
    number = await repo.next_number()
    case = Case(
        organization_id=org_id,
        number=number,
        title=body.case_title or a.title,
        description=a.description,
        severity=body.case_severity or a.severity,
        tlp=a.tlp,
        pap=a.pap,
        status="Open",
        stage="open",
        tags=list(a.tags),
        custom_fields=dict(a.custom_fields),
        created_by=user.user_id,
    )
    db.add(case)
    await db.flush()
    a.case_id = case.id
    a.status = "Imported"
    a.imported_at = datetime.now(tz=UTC)
    await db.flush()
    await audit_and_emit(
        db,
        actor_user_id=user.user_id,
        organization_id=org_id,
        action="promoted",
        entity_type="alert",
        entity_id=a.id,
        diff={"case_id": str(case.id), "case_number": case.number},
    )
    return {"case_id": str(case.id), "case_number": case.number, "alert_id": str(a.id)}


class AlertTimelineEntry(BaseModel):
    id: UUID
    action: str
    entity_type: str
    actor_user_id: UUID | None
    created_at: datetime
    diff: dict[str, Any]


class AlertTimelineResponse(BaseModel):
    alert_id: UUID
    entries: list[AlertTimelineEntry]


@router.get("/{alert_id}/timeline", response_model=AlertTimelineResponse)
async def alert_timeline(
    alert_id: UUID,
    _user: Annotated[CurrentUser, Depends(require_permission("viewAlert"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 100,
    since: datetime | None = None,
    action: str | None = None,
) -> AlertTimelineResponse:
    """Per-alert audit feed: direct entity_type='alert' rows + any audit
    row whose diff JSON references this alert id (covers e.g. responder
    invocations that target the alert). Optional `since=<ISO>` and
    `action=<name>` mirror the RC192 case-timeline filter surface."""
    from sqlalchemy import Text, or_

    a = (
        await db.execute(select(Alert).where(Alert.id == alert_id, Alert.organization_id == org_id))
    ).scalar_one_or_none()
    if a is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "alert_not_found")
    safe_limit = max(1, min(500, int(limit)))
    aid_str = str(alert_id)
    from sqlalchemy import desc as _desc

    from adhkar.db.models import AuditLog

    stmt = (
        select(AuditLog)
        .where(
            AuditLog.organization_id == org_id,
            or_(
                (AuditLog.entity_type == "alert") & (AuditLog.entity_id == alert_id),
                AuditLog.diff.cast(Text).contains(aid_str),
            ),
        )
        .order_by(_desc(AuditLog.created_at))
        .limit(safe_limit)
    )
    if since is not None:
        stmt = stmt.where(AuditLog.created_at >= since)
    if action is not None:
        stmt = stmt.where(AuditLog.action == action)
    rows = (await db.execute(stmt)).scalars().all()
    return AlertTimelineResponse(
        alert_id=alert_id,
        entries=[
            AlertTimelineEntry(
                id=r.id,
                action=r.action,
                entity_type=r.entity_type,
                actor_user_id=r.actor_user_id,
                created_at=r.created_at,
                diff=r.diff or {},
            )
            for r in rows
        ],
    )


@router.post("/{alert_id}/merge/{case_id}", response_model=AlertDTO)
async def merge_alert_into_case(
    alert_id: UUID,
    case_id: UUID,
    _user: Annotated[CurrentUser, Depends(require_permission("manageCase"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AlertDTO:
    a = (
        await db.execute(select(Alert).where(Alert.id == alert_id, Alert.organization_id == org_id))
    ).scalar_one_or_none()
    if not a:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "alert_not_found")
    if a.case_id is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "alert_already_linked_to_case")
    c = (
        await db.execute(
            select(Case).where(
                Case.id == case_id, Case.organization_id == org_id, Case.deleted_at.is_(None)
            )
        )
    ).scalar_one_or_none()
    if not c:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "case_not_found")
    a.case_id = c.id
    a.status = "Imported"
    a.imported_at = datetime.now(tz=UTC)
    await db.flush()
    return _alert_dto(a)
