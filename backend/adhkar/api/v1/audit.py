"""Audit log read endpoint."""

from __future__ import annotations

import csv
import io
import json as _json
from datetime import datetime
from collections.abc import Sequence
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from sqlalchemy import desc, select
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
    _user: Annotated[CurrentUser, Depends(require_permission("viewAudit"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(100, ge=1, le=500),
    entity_type: str | None = None,
    action: str | None = None,
    actor_user_id: UUID | None = None,
) -> list[AuditLogDTO]:
    stmt = (
        select(AuditLog)
        .where(AuditLog.organization_id == org_id)
        .order_by(desc(AuditLog.created_at))
        .limit(limit)
    )
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if actor_user_id:
        stmt = stmt.where(AuditLog.actor_user_id == actor_user_id)
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
    action: str | None = None,
    actor_user_id: UUID | None = None,
    limit: int = Query(5000, ge=1, le=50_000),
) -> PlainTextResponse:
    """CSV dump of audit_logs in the current org. Caps at 50k rows so a
    chatty integration can't OOM the server; tighten via `limit` to
    snapshot a date window."""
    stmt = (
        select(AuditLog)
        .where(AuditLog.organization_id == org_id)
        .order_by(desc(AuditLog.created_at))
        .limit(limit)
    )
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if actor_user_id:
        stmt = stmt.where(AuditLog.actor_user_id == actor_user_id)
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
