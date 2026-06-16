"""Audit log read endpoint."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
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
