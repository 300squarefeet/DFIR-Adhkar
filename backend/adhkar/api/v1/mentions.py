"""Mentions inbox: lists @-mentions targeting the current user."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from adhkar.api.deps import CurrentUser, get_current_user, get_db, require_current_org
from adhkar.db.models import AuditLog, User

router = APIRouter(tags=["mentions"])


class MentionRow(BaseModel):
    id: UUID
    actor_user_id: UUID | None
    created_at: datetime
    diff: dict[str, Any]


class UnreadCount(BaseModel):
    unread: int
    last_seen_at: datetime | None


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


@router.get("/v1/mentions/me/unread", response_model=UnreadCount)
async def unread_mention_count(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UnreadCount:
    """Mentions newer than the user's last_mentions_seen_at, scoped to org."""
    me = (await db.execute(select(User).where(User.id == user.user_id))).scalar_one_or_none()
    last_seen = me.last_mentions_seen_at if me else None
    stmt = select(func.count(AuditLog.id)).where(
        AuditLog.organization_id == org_id,
        AuditLog.entity_type == "user",
        AuditLog.entity_id == user.user_id,
        AuditLog.action == "mentioned",
    )
    if last_seen is not None:
        stmt = stmt.where(AuditLog.created_at > last_seen)
    unread = int((await db.execute(stmt)).scalar_one() or 0)
    return UnreadCount(unread=unread, last_seen_at=last_seen)


@router.post("/v1/mentions/me/seen", status_code=status.HTTP_204_NO_CONTENT)
async def mark_mentions_seen(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    me = (await db.execute(select(User).where(User.id == user.user_id))).scalar_one_or_none()
    if me is None:
        return
    me.last_mentions_seen_at = datetime.now(tz=UTC)
    await db.flush()
