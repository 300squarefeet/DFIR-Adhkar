"""ToolSpec catalog — same shape across LLM providers.

The ToolUse runtime feeds these into the provider-specific format (Anthropic
tool_use, OpenAI tools, Ollama function-call), receives back tool_call
requests, dispatches them against an org-scoped AsyncSession, and feeds the
results back into the conversation until the LLM stops calling tools."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from adhkar.db.models import Alert, Case, Observable

ToolHandler = Callable[[AsyncSession, UUID, dict[str, Any]], Awaitable[str]]


@dataclass(frozen=True, slots=True)
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: ToolHandler


async def _search_cases(db: AsyncSession, org_id: UUID, args: dict[str, Any]) -> str:
    limit = int(args.get("limit") or 20)
    rows = (
        (
            await db.execute(
                select(Case)
                .where(Case.organization_id == org_id, Case.deleted_at.is_(None))
                .order_by(Case.number.desc())
                .limit(min(100, max(1, limit)))
            )
        )
        .scalars()
        .all()
    )
    return (
        "\n".join(f"#{c.number} {c.title} (sev {c.severity}, {c.stage})" for c in rows)
        or "(no cases)"
    )


async def _get_case(db: AsyncSession, org_id: UUID, args: dict[str, Any]) -> str:
    try:
        cid = UUID(str(args.get("case_id") or ""))
    except ValueError:
        return "error: invalid_case_id"
    c = (
        await db.execute(
            select(Case).where(
                Case.id == cid,
                Case.organization_id == org_id,
                Case.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if not c:
        return "error: case_not_found"
    return (
        f"#{c.number} {c.title}\n"
        f"Severity: {c.severity}  TLP: {c.tlp}  Stage: {c.stage}\n"
        f"Description: {c.description or '(none)'}"
    )


async def _search_observables(db: AsyncSession, org_id: UUID, args: dict[str, Any]) -> str:
    data_type = str(args.get("data_type") or "")
    contains = str(args.get("value_contains") or "")
    limit = int(args.get("limit") or 20)
    stmt = select(Observable).where(
        Observable.organization_id == org_id, Observable.deleted_at.is_(None)
    )
    if data_type:
        stmt = stmt.where(Observable.data_type == data_type)
    if contains:
        stmt = stmt.where(Observable.data.ilike(f"%{contains}%"))
    rows = (await db.execute(stmt.limit(min(100, max(1, limit))))).scalars().all()
    return "\n".join(f"{o.data_type}: {o.data}" for o in rows) or "(none)"


async def _search_alerts(db: AsyncSession, org_id: UUID, args: dict[str, Any]) -> str:
    limit = int(args.get("limit") or 20)
    status_arg = str(args.get("status") or "")
    stmt = select(Alert).where(Alert.organization_id == org_id)
    if status_arg:
        stmt = stmt.where(Alert.status == status_arg)
    stmt = stmt.order_by(Alert.created_at.desc()).limit(min(100, max(1, limit)))
    rows = (await db.execute(stmt)).scalars().all()
    return (
        "\n".join(
            f"{a.source}/{a.source_ref}: {a.title} (sev {a.severity}, {a.status})" for a in rows
        )
        or "(no alerts)"
    )


TOOL_CATALOG: list[ToolSpec] = [
    ToolSpec(
        name="search_cases",
        description="List recent cases in the caller's organization.",
        input_schema={
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "minimum": 1, "maximum": 100},
            },
        },
        handler=_search_cases,
    ),
    ToolSpec(
        name="get_case",
        description="Fetch a single case by UUID.",
        input_schema={
            "type": "object",
            "properties": {"case_id": {"type": "string"}},
            "required": ["case_id"],
        },
        handler=_get_case,
    ),
    ToolSpec(
        name="search_observables",
        description=(
            "List observables; optional filter by data_type "
            "(ip, domain, url, hash, etc.) and substring."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "data_type": {"type": "string"},
                "value_contains": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 100},
            },
        },
        handler=_search_observables,
    ),
    ToolSpec(
        name="search_alerts",
        description="List recent alerts, optionally filtered by status.",
        input_schema={
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["New", "Updated", "Ignored", "Imported"],
                },
                "limit": {"type": "integer", "minimum": 1, "maximum": 100},
            },
        },
        handler=_search_alerts,
    ),
]


def get_tool(name: str) -> ToolSpec | None:
    for t in TOOL_CATALOG:
        if t.name == name:
            return t
    return None
