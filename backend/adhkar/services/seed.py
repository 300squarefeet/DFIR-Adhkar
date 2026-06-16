"""Seed default profiles into a freshly created organization."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from adhkar.auth.permissions import DEFAULT_PROFILES
from adhkar.db.models import Profile


async def seed_default_profiles(session: AsyncSession, organization_id: UUID) -> dict[str, UUID]:
    """Insert org-admin, analyst, read-only, portal-user profiles. Returns name → id map."""
    name_to_id: dict[str, UUID] = {}
    for name, perms in DEFAULT_PROFILES.items():
        p = Profile(
            organization_id=organization_id,
            name=name,
            description=f"Default {name} profile",
            permissions=sorted(perms),
            is_default=True,
        )
        session.add(p)
        await session.flush()
        name_to_id[name] = p.id
    return name_to_id
