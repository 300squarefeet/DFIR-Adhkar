"""Responder catalog + invocation endpoints (Phase 5+ extension)."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from adhkar.api.deps import (
    CurrentUser,
    get_db,
    require_current_org,
    require_permission,
)
from adhkar.audit import audit_and_emit
from adhkar.db.models import Alert, Case, Observable
from adhkar.responders.base import Responder, get_responder_registry
from adhkar.responders.webhook_notify import WebhookNotifyResponder

router = APIRouter(prefix="/v1/responders", tags=["responders"])

# Bootstrap built-in responders once.
_BOOTSTRAPPED = False


def _bootstrap_once() -> None:
    global _BOOTSTRAPPED
    if _BOOTSTRAPPED:
        return
    reg = get_responder_registry()
    reg.register(WebhookNotifyResponder())
    _BOOTSTRAPPED = True


_bootstrap_once()


class ResponderDTO(BaseModel):
    name: str
    description: str
    supported_entity_types: list[str]
    confirm_required: bool


def _to_dto(r: Responder) -> ResponderDTO:
    return ResponderDTO(
        name=r.name,
        description=r.description,
        supported_entity_types=sorted(r.supported_entity_types),
        confirm_required=r.confirm_required,
    )


class InvokePayload(BaseModel):
    payload: dict[str, Any] = Field(default_factory=dict)


class InvokeResult(BaseModel):
    status: str
    summary: str
    details: dict[str, Any]


@router.get("", response_model=list[ResponderDTO])
async def list_responders(
    _user: Annotated[CurrentUser, Depends(require_permission("viewCase"))],
) -> list[ResponderDTO]:
    return [_to_dto(r) for r in get_responder_registry().all()]


async def _entity_exists(db: AsyncSession, org_id: UUID, entity_type: str, entity_id: UUID) -> bool:
    if entity_type == "case":
        row = await db.execute(
            select(Case.id).where(
                Case.id == entity_id, Case.organization_id == org_id, Case.deleted_at.is_(None)
            )
        )
    elif entity_type == "alert":
        row = await db.execute(
            select(Alert.id).where(Alert.id == entity_id, Alert.organization_id == org_id)
        )
    elif entity_type == "observable":
        row = await db.execute(
            select(Observable.id).where(
                Observable.id == entity_id,
                Observable.organization_id == org_id,
                Observable.deleted_at.is_(None),
            )
        )
    else:
        return False
    return row.scalar_one_or_none() is not None


@router.post(
    "/{name}/{entity_type}/{entity_id}",
    response_model=InvokeResult,
)
async def invoke_responder(
    name: str,
    entity_type: str,
    entity_id: UUID,
    body: InvokePayload,
    user: Annotated[CurrentUser, Depends(require_permission("manageCase"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> InvokeResult:
    responder = get_responder_registry().get(name)
    if not responder:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "responder_not_found")
    if entity_type not in responder.supported_entity_types:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "responder_does_not_support_entity_type")
    if not await _entity_exists(db, org_id, entity_type, entity_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "entity_not_found")
    result = await responder.run(entity_type, str(entity_id), body.payload)
    await audit_and_emit(
        db,
        actor_user_id=user.user_id,
        organization_id=org_id,
        action="invoked",
        entity_type="responder",
        entity_id=None,
        diff={
            "responder": name,
            "target_type": entity_type,
            "target_id": str(entity_id),
            "result": result.status,
            "summary": result.summary,
        },
    )
    return InvokeResult(status=result.status, summary=result.summary, details=result.details)
