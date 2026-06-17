"""Audit log read endpoint."""

from __future__ import annotations

import csv
import io
import json as _json
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy import func as _sqlfunc
from sqlalchemy.ext.asyncio import AsyncSession

from adhkar.api.deps import CurrentUser, get_db, require_current_org, require_permission
from adhkar.db.models import AuditLog

router = APIRouter(prefix="/v1/audit", tags=["audit"])


class AuditLogDTO(BaseModel):
    id: UUID
    actor_user_id: UUID | None
    organization_id: UUID | None
    action: str
    entity_type: str
    entity_id: UUID | None
    diff: dict[str, Any]
    request_id: str | None
    ip: str | None
    created_at: datetime


@router.get("", response_model=list[AuditLogDTO])
async def list_audit(
    user: Annotated[CurrentUser, Depends(require_permission("viewAudit"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0, le=100_000),
    entity_type: str | None = None,
    entity_id: UUID | None = None,
    action: str | None = None,
    actor_user_id: UUID | None = None,
    me: bool | None = None,
    ip: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
) -> list[AuditLogDTO]:
    """`me=true` is a shorthand for actor_user_id=<current user>."""
    if me is True:
        actor_user_id = user.user_id
    stmt = (
        select(AuditLog)
        .where(AuditLog.organization_id == org_id)
        .order_by(desc(AuditLog.created_at))
        .offset(offset)
        .limit(limit)
    )
    if ip:
        stmt = stmt.where(AuditLog.ip == ip)
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if entity_id is not None:
        stmt = stmt.where(AuditLog.entity_id == entity_id)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if actor_user_id:
        stmt = stmt.where(AuditLog.actor_user_id == actor_user_id)
    if since is not None:
        stmt = stmt.where(AuditLog.created_at >= since)
    if until is not None:
        stmt = stmt.where(AuditLog.created_at < until)
    rows = (await db.execute(stmt)).scalars().all()
    return _to_dtos(rows)


def _to_dtos(rows: Sequence[AuditLog]) -> list[AuditLogDTO]:
    return [
        AuditLogDTO(
            id=r.id,
            actor_user_id=r.actor_user_id,
            organization_id=r.organization_id,
            action=r.action,
            entity_type=r.entity_type,
            entity_id=r.entity_id,
            diff=r.diff,
            request_id=r.request_id,
            ip=str(r.ip) if r.ip else None,
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.get(
    "/export-csv",
    response_class=PlainTextResponse,
    responses={200: {"content": {"text/csv": {}}}},
)
async def export_audit_csv(
    _user: Annotated[CurrentUser, Depends(require_permission("viewAudit"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
    entity_type: str | None = None,
    entity_id: UUID | None = None,
    action: str | None = None,
    actor_user_id: UUID | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = Query(5000, ge=1, le=50_000),
) -> PlainTextResponse:
    """CSV dump of audit_logs in the current org. Caps at 50k rows so a
    chatty integration can't OOM the server; pass `since`/`until` to
    snapshot a date window."""
    stmt = (
        select(AuditLog)
        .where(AuditLog.organization_id == org_id)
        .order_by(desc(AuditLog.created_at))
        .limit(limit)
    )
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if entity_id is not None:
        stmt = stmt.where(AuditLog.entity_id == entity_id)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if actor_user_id:
        stmt = stmt.where(AuditLog.actor_user_id == actor_user_id)
    if since is not None:
        stmt = stmt.where(AuditLog.created_at >= since)
    if until is not None:
        stmt = stmt.where(AuditLog.created_at < until)
    rows = (await db.execute(stmt)).scalars().all()
    buf = io.StringIO()
    w = csv.writer(buf, quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
    w.writerow(
        [
            "created_at",
            "actor_user_id",
            "action",
            "entity_type",
            "entity_id",
            "diff",
            "request_id",
            "ip",
        ]
    )
    for r in rows:
        w.writerow(
            [
                r.created_at.isoformat(),
                str(r.actor_user_id) if r.actor_user_id else "",
                r.action,
                r.entity_type,
                str(r.entity_id) if r.entity_id else "",
                _json.dumps(r.diff, separators=(",", ":"), sort_keys=True),
                r.request_id or "",
                str(r.ip) if r.ip else "",
            ]
        )
    return PlainTextResponse(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="adhkar-audit.csv"'},
    )


class AuditSummaryRow(BaseModel):
    entity_type: str
    action: str
    count: int


class AuditSummaryResponse(BaseModel):
    window_days: int
    rows: list[AuditSummaryRow]


@router.get("/summary", response_model=AuditSummaryResponse)
async def audit_summary(
    _user: Annotated[CurrentUser, Depends(require_permission("viewAudit"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
    days: int = Query(default=14, ge=1, le=90),
    actor_user_id: UUID | None = None,
    entity_type: str | None = None,
) -> AuditSummaryResponse:
    """Audit row counts grouped by (entity_type, action) over the last N days.
    Sorted by count DESC then entity_type then action so the most-noisy
    surfaces sort first. Useful for spotting noisy automation or a sudden
    spike of mutations on one entity family. Optional `actor_user_id`
    scopes to one actor's noise; optional `entity_type` scopes to one
    entity family."""
    since = datetime.now(tz=UTC) - timedelta(days=days)
    stmt = (
        select(
            AuditLog.entity_type,
            AuditLog.action,
            _sqlfunc.count().label("n"),
        )
        .where(AuditLog.organization_id == org_id, AuditLog.created_at >= since)
        .group_by(AuditLog.entity_type, AuditLog.action)
    )
    if actor_user_id is not None:
        stmt = stmt.where(AuditLog.actor_user_id == actor_user_id)
    if entity_type is not None:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    rows = (await db.execute(stmt)).all()
    out = [AuditSummaryRow(entity_type=str(r[0]), action=str(r[1]), count=int(r[2])) for r in rows]
    out.sort(key=lambda r: (-r.count, r.entity_type, r.action))
    return AuditSummaryResponse(window_days=days, rows=out)
