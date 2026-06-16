"""OrgScopedRepository abstract base.

Phase 2+ domain entities (Observable, Case, Alert) extend this and inherit
automatic org filtering for every query.
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar
from uuid import UUID

from sqlalchemy import Select, delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase

T = TypeVar("T", bound=DeclarativeBase)


class OrgScopedRepository(Generic[T]):
    """Base class — subclasses set `model: type[T]` and inherit org-scoped CRUD.

    Every method automatically applies WHERE organization_id = current_org_id.
    Subclasses cannot opt out (by design).
    """

    model: type[T]

    def __init__(self, session: AsyncSession, current_org_id: UUID) -> None:
        if current_org_id is None:
            raise ValueError("current_org_id is required")
        self.session = session
        self.current_org_id = current_org_id

    def _scoped(self, stmt: Select[Any]) -> Select[Any]:
        org_col = self.model.organization_id  # type: ignore[attr-defined]
        return stmt.where(org_col == self.current_org_id)

    async def list(self) -> list[T]:
        rows = (await self.session.execute(self._scoped(select(self.model)))).scalars().all()
        return list(rows)

    async def get(self, entity_id: UUID) -> T | None:
        stmt = self._scoped(select(self.model).where(self.model.id == entity_id))  # type: ignore[attr-defined]
        return (await self.session.execute(stmt)).scalar_one_or_none()  # type: ignore[no-any-return]

    async def add(self, entity: T) -> T:
        """Insert. Subclasses are responsible for setting organization_id correctly
        (typically `entity.organization_id = self.current_org_id` before calling add)."""
        # Safety: enforce the org_id matches current_org_id.
        org_attr = getattr(entity, "organization_id", None)
        if org_attr is not None and org_attr != self.current_org_id:
            raise ValueError("entity.organization_id mismatch")
        if org_attr is None:
            entity.organization_id = self.current_org_id  # type: ignore[attr-defined]
        self.session.add(entity)
        await self.session.flush()
        return entity

    async def delete(self, entity_id: UUID) -> bool:
        org_col = self.model.organization_id  # type: ignore[attr-defined]
        id_col = self.model.id  # type: ignore[attr-defined]
        stmt = delete(self.model).where(id_col == entity_id, org_col == self.current_org_id)
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount > 0  # type: ignore[attr-defined,no-any-return]
