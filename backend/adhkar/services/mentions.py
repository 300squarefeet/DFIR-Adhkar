"""Parse @<display_name> tokens and emit 'mentioned' outbox events.

Single source of truth used by both comment-create and task-log-create
endpoints so notification semantics stay consistent.
"""

from __future__ import annotations

import re
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from adhkar.audit import audit_and_emit
from adhkar.db.models import User, UserOrgMembership

MENTION_RE = re.compile(r"@([A-Za-z0-9_.-]+(?:\s[A-Za-z0-9_.-]+)*)")


async def emit_mentions(
    db: AsyncSession,
    *,
    org_id: UUID,
    actor_user_id: UUID,
    content: str,
    extra_diff: dict[str, Any],
) -> int:
    """Resolve `@<name>` tokens to org members and emit one 'mentioned'
    audit+outbox event per match. Returns the number of users notified."""
    candidates = {m.group(1).strip() for m in MENTION_RE.finditer(content)}
    if not candidates:
        return 0
    rows = (
        (
            await db.execute(
                select(User)
                .join(UserOrgMembership, UserOrgMembership.user_id == User.id)
                .where(
                    UserOrgMembership.organization_id == org_id,
                    User.deleted_at.is_(None),
                    User.display_name.in_(list(candidates)),
                )
            )
        )
        .scalars()
        .all()
    )
    for u in rows:
        await audit_and_emit(
            db,
            actor_user_id=actor_user_id,
            organization_id=org_id,
            action="mentioned",
            entity_type="user",
            entity_id=u.id,
            diff={**extra_diff, "mentioned_display_name": u.display_name},
        )
    return len(rows)
