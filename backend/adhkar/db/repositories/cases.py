"""Case repository."""

from __future__ import annotations

from sqlalchemy import func, select

from adhkar.db.models import Case
from adhkar.db.repositories.base import OrgScopedRepository


class CaseRepository(OrgScopedRepository[Case]):
    model = Case

    async def next_number(self) -> int:
        """Per-org sequential case number. Race-protected by the
        unique(organization_id, number) constraint — callers retry on conflict."""
        result = await self.session.execute(
            select(func.coalesce(func.max(Case.number), 0)).where(
                Case.organization_id == self.current_org_id
            )
        )
        return int(result.scalar_one()) + 1
