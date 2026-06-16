"""Taxonomy management endpoints (Phase 6 extras).

CRUD over the namespace:predicate=value vocabulary. Import accepts a
MISP-style JSON manifest:
    {
      "namespace": "tlp",
      "predicates": [{"value": "white", "description": "..."}, ...],
      "values": [{"predicate": "white", "entry": [...]}, ...]
    }
Only the flat (namespace, predicate, value) triple is stored so search/
filter stays SQL-fast."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from adhkar.api.deps import (
    CurrentUser,
    get_db,
    require_current_org,
    require_permission,
)
from adhkar.db.models import TaxonomyEntry

router = APIRouter(prefix="/v1/taxonomies", tags=["taxonomies"])


class TaxonomyEntryDTO(BaseModel):
    id: UUID
    namespace: str
    predicate: str
    value: str
    description: str | None
    color: str | None


class TaxonomyEntryCreate(BaseModel):
    namespace: str = Field(min_length=1, max_length=100)
    predicate: str = Field(min_length=1, max_length=100)
    value: str = Field(min_length=1, max_length=200)
    description: str | None = None
    color: str | None = Field(default=None, max_length=20)


class TaxonomyImportPayload(BaseModel):
    namespace: str = Field(min_length=1, max_length=100)
    predicates: list[dict[str, Any]] = Field(default_factory=list)
    values: list[dict[str, Any]] = Field(default_factory=list)


class TaxonomyImportResult(BaseModel):
    imported: int
    skipped_duplicate: int


def _to_dto(t: TaxonomyEntry) -> TaxonomyEntryDTO:
    return TaxonomyEntryDTO(
        id=t.id,
        namespace=t.namespace,
        predicate=t.predicate,
        value=t.value,
        description=t.description,
        color=t.color,
    )


@router.get("", response_model=list[TaxonomyEntryDTO])
async def list_taxonomy_entries(
    _user: Annotated[CurrentUser, Depends(require_permission("viewCase"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
    namespace: str | None = None,
) -> list[TaxonomyEntryDTO]:
    stmt = select(TaxonomyEntry).where(TaxonomyEntry.organization_id == org_id)
    if namespace:
        stmt = stmt.where(TaxonomyEntry.namespace == namespace)
    stmt = stmt.order_by(TaxonomyEntry.namespace, TaxonomyEntry.predicate, TaxonomyEntry.value)
    rows = (await db.execute(stmt)).scalars().all()
    return [_to_dto(t) for t in rows]


@router.post("", response_model=TaxonomyEntryDTO, status_code=status.HTTP_201_CREATED)
async def create_taxonomy_entry(
    body: TaxonomyEntryCreate,
    _user: Annotated[CurrentUser, Depends(require_permission("manageConfig"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TaxonomyEntryDTO:
    t = TaxonomyEntry(
        organization_id=org_id,
        namespace=body.namespace,
        predicate=body.predicate,
        value=body.value,
        description=body.description,
        color=body.color,
    )
    db.add(t)
    try:
        await db.flush()
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "taxonomy_entry_exists") from e
    return _to_dto(t)


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_taxonomy_entry(
    entry_id: UUID,
    _user: Annotated[CurrentUser, Depends(require_permission("manageConfig"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    t = (
        await db.execute(
            select(TaxonomyEntry).where(
                TaxonomyEntry.id == entry_id, TaxonomyEntry.organization_id == org_id
            )
        )
    ).scalar_one_or_none()
    if t is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "taxonomy_entry_not_found")
    await db.delete(t)
    await db.flush()


@router.post("/import-misp", response_model=TaxonomyImportResult)
async def import_misp_taxonomy(
    body: TaxonomyImportPayload,
    _user: Annotated[CurrentUser, Depends(require_permission("manageConfig"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TaxonomyImportResult:
    """Walk the MISP manifest and persist each (namespace, predicate, value).

    The MISP shape nests `values[*].entry[]` under predicates; both flat
    `predicates` (no values) and the nested form are accepted."""
    imported = 0
    duplicate = 0
    predicate_descriptions: dict[str, str | None] = {
        str(p.get("value")): p.get("expanded") or p.get("description")
        for p in body.predicates
        if isinstance(p, dict) and p.get("value")
    }
    for entry_group in body.values:
        if not isinstance(entry_group, dict):
            continue
        predicate = str(entry_group.get("predicate") or "")
        if not predicate:
            continue
        for inner in entry_group.get("entry", []) or []:
            if not isinstance(inner, dict):
                continue
            value = str(inner.get("value") or "")
            if not value:
                continue
            description = (
                inner.get("expanded")
                or inner.get("description")
                or predicate_descriptions.get(predicate)
            )
            color = inner.get("colour") or inner.get("color")
            row = TaxonomyEntry(
                organization_id=org_id,
                namespace=body.namespace,
                predicate=predicate,
                value=value,
                description=description if isinstance(description, str) else None,
                color=color if isinstance(color, str) else None,
            )
            db.add(row)
            try:
                await db.flush()
                imported += 1
            except IntegrityError:
                await db.rollback()
                duplicate += 1
    # Also persist any predicates supplied without nested entries — useful
    # for taxonomies that only enumerate predicate-level labels.
    if not body.values:
        for pred, desc in predicate_descriptions.items():
            row = TaxonomyEntry(
                organization_id=org_id,
                namespace=body.namespace,
                predicate=pred,
                value="*",
                description=desc if isinstance(desc, str) else None,
            )
            db.add(row)
            try:
                await db.flush()
                imported += 1
            except IntegrityError:
                await db.rollback()
                duplicate += 1
    return TaxonomyImportResult(imported=imported, skipped_duplicate=duplicate)
