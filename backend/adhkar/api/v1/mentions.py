"""Mentions inbox: lists @-mentions targeting the current user."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from adhkar.api.deps import CurrentUser, get_current_user, get_db, require_current_org
from adhkar.db.models import AuditLog

router = APIRouter(tags=["mentions"])


class MentionRow(BaseModel):
    id: UUID
    actor_user_id: UUID | None
    created_at: datetime
    diff: dict[str, Any]


@router.get("/v1/mentions/me", response_model=list[MentionRow])
async def list_my_mentions(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 50,
) -> list[MentionRow]:
    """Return audit_log rows where the current user was @-mentioned in the
    current org, newest first. Capped at 200 to keep payloads bounded."""
    safe_limit = max(1, min(200, int(limit)))
    rows = (
        (
            await db.execute(
                select(AuditLog)
                .where(
                    AuditLog.organization_id == org_id,
                    AuditLog.entity_type == "user",
                    AuditLog.entity_id == user.user_id,
                    AuditLog.action == "mentioned",
                )
                .order_by(AuditLog.created_at.desc())
                .limit(safe_limit)
            )
        )
        .scalars()
        .all()
    )
    return [
        MentionRow(
            id=r.id,
            actor_user_id=r.actor_user_id,
            created_at=r.created_at,
            diff=dict(r.diff),
        )
        for r in rows
    ]
