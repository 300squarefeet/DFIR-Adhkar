"""Notification endpoints + rules CRUD (Phase 7)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from adhkar.api.deps import (
    CurrentUser,
    get_db,
    require_current_org,
    require_permission,
)
from adhkar.db.models import NotificationDelivery, NotificationEndpoint, NotificationRule

router = APIRouter(tags=["notifications"])

ENDPOINT_KIND = Literal["webhook", "slack", "teams", "mattermost", "email"]


# ---------- Endpoints ----------


class EndpointDTO(BaseModel):
    id: UUID
    name: str
    kind: str
    config: dict[str, Any]
    enabled: bool
    created_at: datetime
    updated_at: datetime


class EndpointCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    kind: ENDPOINT_KIND
    config: dict[str, Any] = {}
    enabled: bool = True


class EndpointPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    config: dict[str, Any] | None = None
    enabled: bool | None = None


def _endpoint_dto(e: NotificationEndpoint) -> EndpointDTO:
    return EndpointDTO(
        id=e.id,
        name=e.name,
        kind=e.kind,
        config=dict(e.config),
        enabled=e.enabled,
        created_at=e.created_at,
        updated_at=e.updated_at,
    )


@router.get("/v1/notification-endpoints", response_model=list[EndpointDTO])
async def list_endpoints(
    _user: Annotated[CurrentUser, Depends(require_permission("manageConfig"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[EndpointDTO]:
    rows = (
        (
            await db.execute(
                select(NotificationEndpoint)
                .where(NotificationEndpoint.organization_id == org_id)
                .order_by(NotificationEndpoint.name)
            )
        )
        .scalars()
        .all()
    )
    return [_endpoint_dto(e) for e in rows]


@router.post(
    "/v1/notification-endpoints", response_model=EndpointDTO, status_code=status.HTTP_201_CREATED
)
async def create_endpoint(
    body: EndpointCreate,
    user: Annotated[CurrentUser, Depends(require_permission("manageConfig"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> EndpointDTO:
    e = NotificationEndpoint(
        organization_id=org_id,
        name=body.name,
        kind=body.kind,
        config=body.config,
        enabled=body.enabled,
        created_by=user.user_id,
    )
    db.add(e)
    try:
        await db.flush()
    except IntegrityError as ex:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "endpoint_name_taken") from ex
    return _endpoint_dto(e)


@router.patch("/v1/notification-endpoints/{endpoint_id}", response_model=EndpointDTO)
async def patch_endpoint(
    endpoint_id: UUID,
    body: EndpointPatch,
    _user: Annotated[CurrentUser, Depends(require_permission("manageConfig"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> EndpointDTO:
    e = (
        await db.execute(
            select(NotificationEndpoint).where(
                NotificationEndpoint.id == endpoint_id,
                NotificationEndpoint.organization_id == org_id,
            )
        )
    ).scalar_one_or_none()
    if not e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "endpoint_not_found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(e, field, value)
    await db.flush()
    return _endpoint_dto(e)


@router.delete("/v1/notification-endpoints/{endpoint_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_endpoint(
    endpoint_id: UUID,
    _user: Annotated[CurrentUser, Depends(require_permission("manageConfig"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    e = (
        await db.execute(
            select(NotificationEndpoint).where(
                NotificationEndpoint.id == endpoint_id,
                NotificationEndpoint.organization_id == org_id,
            )
        )
    ).scalar_one_or_none()
    if not e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "endpoint_not_found")
    await db.delete(e)
    await db.flush()


# ---------- Rules ----------


class RuleDTO(BaseModel):
    id: UUID
    name: str
    description: str | None
    event_filter: dict[str, Any]
    endpoint_ids: list[str]
    enabled: bool
    created_at: datetime
    updated_at: datetime


class RuleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    event_filter: dict[str, Any]
    endpoint_ids: list[UUID]
    enabled: bool = True


class RulePatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    event_filter: dict[str, Any] | None = None
    endpoint_ids: list[UUID] | None = None
    enabled: bool | None = None


def _rule_dto(r: NotificationRule) -> RuleDTO:
    return RuleDTO(
        id=r.id,
        name=r.name,
        description=r.description,
        event_filter=dict(r.event_filter),
        endpoint_ids=list(r.endpoint_ids),
        enabled=r.enabled,
        created_at=r.created_at,
        updated_at=r.updated_at,
    )


async def _verify_endpoints(db: AsyncSession, org_id: UUID, endpoint_ids: list[UUID]) -> None:
    if not endpoint_ids:
        return
    rows = (
        (
            await db.execute(
                select(NotificationEndpoint.id).where(
                    NotificationEndpoint.organization_id == org_id,
                    NotificationEndpoint.id.in_(endpoint_ids),
                )
            )
        )
        .scalars()
        .all()
    )
    if len(rows) != len(set(endpoint_ids)):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "unknown_endpoint_in_list")


@router.get("/v1/notification-rules", response_model=list[RuleDTO])
async def list_rules(
    _user: Annotated[CurrentUser, Depends(require_permission("manageConfig"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[RuleDTO]:
    rows = (
        (
            await db.execute(
                select(NotificationRule)
                .where(NotificationRule.organization_id == org_id)
                .order_by(NotificationRule.name)
            )
        )
        .scalars()
        .all()
    )
    return [_rule_dto(r) for r in rows]


@router.post("/v1/notification-rules", response_model=RuleDTO, status_code=status.HTTP_201_CREATED)
async def create_rule(
    body: RuleCreate,
    user: Annotated[CurrentUser, Depends(require_permission("manageConfig"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RuleDTO:
    await _verify_endpoints(db, org_id, body.endpoint_ids)
    r = NotificationRule(
        organization_id=org_id,
        name=body.name,
        description=body.description,
        event_filter=body.event_filter,
        endpoint_ids=[str(eid) for eid in body.endpoint_ids],
        enabled=body.enabled,
        created_by=user.user_id,
    )
    db.add(r)
    try:
        await db.flush()
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "rule_name_taken") from e
    return _rule_dto(r)


@router.patch("/v1/notification-rules/{rule_id}", response_model=RuleDTO)
async def patch_rule(
    rule_id: UUID,
    body: RulePatch,
    _user: Annotated[CurrentUser, Depends(require_permission("manageConfig"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RuleDTO:
    r = (
        await db.execute(
            select(NotificationRule).where(
                NotificationRule.id == rule_id, NotificationRule.organization_id == org_id
            )
        )
    ).scalar_one_or_none()
    if not r:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "rule_not_found")
    patch = body.model_dump(exclude_unset=True)
    if "endpoint_ids" in patch and patch["endpoint_ids"] is not None:
        eid_list = [UUID(str(e)) for e in patch["endpoint_ids"]]
        await _verify_endpoints(db, org_id, eid_list)
        patch["endpoint_ids"] = [str(e) for e in eid_list]
    for field, value in patch.items():
        setattr(r, field, value)
    await db.flush()
    return _rule_dto(r)


@router.delete("/v1/notification-rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule(
    rule_id: UUID,
    _user: Annotated[CurrentUser, Depends(require_permission("manageConfig"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    r = (
        await db.execute(
            select(NotificationRule).where(
                NotificationRule.id == rule_id, NotificationRule.organization_id == org_id
            )
        )
    ).scalar_one_or_none()
    if not r:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "rule_not_found")
    await db.delete(r)
    await db.flush()


# ---------- Deliveries (read-only) ----------


class DeliveryDTO(BaseModel):
    id: UUID
    rule_id: UUID | None
    endpoint_id: UUID | None
    event_type: str
    payload: dict[str, Any]
    status: str
    attempts: int
    last_error: str | None
    created_at: datetime
    delivered_at: datetime | None


@router.get("/v1/notification-deliveries", response_model=list[DeliveryDTO])
async def list_deliveries(
    _user: Annotated[CurrentUser, Depends(require_permission("manageConfig"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
    status_filter: Literal["pending", "succeeded", "failed"] | None = None,
    rule_id: UUID | None = None,
    endpoint_id: UUID | None = None,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[DeliveryDTO]:
    """Read-only history of dispatcher attempts. Useful for diagnosing why a
    notification rule isn't firing or which endpoint is rejecting."""
    stmt = (
        select(NotificationDelivery)
        .where(NotificationDelivery.organization_id == org_id)
        .order_by(desc(NotificationDelivery.created_at))
        .limit(limit)
    )
    if status_filter:
        stmt = stmt.where(NotificationDelivery.status == status_filter)
    if rule_id:
        stmt = stmt.where(NotificationDelivery.rule_id == rule_id)
    if endpoint_id:
        stmt = stmt.where(NotificationDelivery.endpoint_id == endpoint_id)
    rows = (await db.execute(stmt)).scalars().all()
    return [
        DeliveryDTO(
            id=d.id,
            rule_id=d.rule_id,
            endpoint_id=d.endpoint_id,
            event_type=d.event_type,
            payload=dict(d.payload),
            status=d.status,
            attempts=d.attempts,
            last_error=d.last_error,
            created_at=d.created_at,
            delivered_at=d.delivered_at,
        )
        for d in rows
    ]
