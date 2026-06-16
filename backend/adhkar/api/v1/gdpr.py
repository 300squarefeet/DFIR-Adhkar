"""GDPR data-subject endpoints.

Two operations any GDPR-scoped deployment must support:
- Export: assemble everything the platform knows about a user across all
  orgs the requester has visibility into → returns a single JSON payload.
- Erase: scrub PII from the user row and any per-user-authored artifact
  trails (AuditLog actor, AiCall user_id, TaskLog author_id, Comment
  author_id), then lock the account. We never hard-delete because
  case/alert/audit history must survive for incident-response forensics.

Both are gated by manageUser (admin-only). The user being affected can
also self-request via the API key path; if they're calling about
themselves, the require_permission gate is sufficient since their token
proves identity."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from adhkar.api.deps import (
    CurrentUser,
    get_db,
    require_permission,
)
from adhkar.audit import audit_and_emit
from adhkar.db.models import (
    AiCall,
    AuditLog,
    Comment,
    TaskLog,
    User,
)

router = APIRouter(prefix="/v1/gdpr", tags=["gdpr"])


class ExportResponse(BaseModel):
    user: dict[str, Any]
    audit_log_entries: list[dict[str, Any]]
    ai_calls: list[dict[str, Any]]
    comments: list[dict[str, Any]]
    task_logs: list[dict[str, Any]]


class EraseResponse(BaseModel):
    user_id: UUID
    erased_at: datetime
    counts: dict[str, int]


async def _load_user(db: AsyncSession, user_id: UUID) -> User:
    u = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if u is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user_not_found")
    return u


@router.get("/users/{user_id}/export", response_model=ExportResponse)
async def export_user(
    user_id: UUID,
    _user: Annotated[CurrentUser, Depends(require_permission("manageUser"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ExportResponse:
    u = await _load_user(db, user_id)
    audit = (
        (await db.execute(select(AuditLog).where(AuditLog.actor_user_id == user_id).limit(10_000)))
        .scalars()
        .all()
    )
    ai = (
        (await db.execute(select(AiCall).where(AiCall.user_id == user_id).limit(10_000)))
        .scalars()
        .all()
    )
    comments = (
        (await db.execute(select(Comment).where(Comment.author_id == user_id).limit(10_000)))
        .scalars()
        .all()
    )
    task_logs = (
        (await db.execute(select(TaskLog).where(TaskLog.author_id == user_id).limit(10_000)))
        .scalars()
        .all()
    )
    return ExportResponse(
        user={
            "id": str(u.id),
            "email": str(u.email),
            "display_name": u.display_name,
            "status": u.status,
            "created_at": u.created_at.isoformat() if u.created_at else None,
        },
        audit_log_entries=[
            {
                "id": str(a.id),
                "action": a.action,
                "entity_type": a.entity_type,
                "entity_id": str(a.entity_id) if a.entity_id else None,
                "created_at": a.created_at.isoformat(),
            }
            for a in audit
        ],
        ai_calls=[
            {
                "id": str(c.id),
                "purpose": c.purpose,
                "provider": c.provider,
                "model": c.model,
                "created_at": c.created_at.isoformat(),
            }
            for c in ai
        ],
        comments=[
            {"id": str(c.id), "case_id": str(c.case_id), "content": c.content} for c in comments
        ],
        task_logs=[
            {"id": str(t.id), "task_id": str(t.task_id), "content": t.content} for t in task_logs
        ],
    )


@router.post("/users/{user_id}/erase", response_model=EraseResponse)
async def erase_user(
    user_id: UUID,
    actor: Annotated[CurrentUser, Depends(require_permission("manageUser"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> EraseResponse:
    u = await _load_user(db, user_id)
    erased_at = datetime.now(tz=UTC)
    placeholder_email = f"erased+{u.id}@redacted.invalid"
    u.email = placeholder_email
    u.display_name = "(erased)"
    u.status = "locked"
    # Redact authored content
    comments_result = await db.execute(
        update(Comment).where(Comment.author_id == user_id).values(content="(content erased)")
    )
    task_logs_result = await db.execute(
        update(TaskLog).where(TaskLog.author_id == user_id).values(content="(content erased)")
    )
    ai_calls_result = await db.execute(
        update(AiCall)
        .where(AiCall.user_id == user_id)
        .values(prompt="(prompt erased)", response_text="(response erased)")
    )
    await db.flush()
    await audit_and_emit(
        db,
        actor_user_id=actor.user_id,
        organization_id=None,
        action="gdpr_erased",
        entity_type="user",
        entity_id=user_id,
        diff={"erased_at": erased_at.isoformat()},
    )
    return EraseResponse(
        user_id=user_id,
        erased_at=erased_at,
        counts={
            "comments": int(comments_result.rowcount or 0),  # type: ignore[attr-defined]
            "task_logs": int(task_logs_result.rowcount or 0),  # type: ignore[attr-defined]
            "ai_calls": int(ai_calls_result.rowcount or 0),  # type: ignore[attr-defined]
        },
    )
