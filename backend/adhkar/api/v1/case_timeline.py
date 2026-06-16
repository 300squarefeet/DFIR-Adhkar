"""Case timeline: synthesizes audit events into a chronological feed.

We don't store a separate Timeline table; the timeline is derived from
AuditLog rows where entity_type='case' and entity_id=case_id, plus rows
where the parent diff explicitly references this case. Cheap, always
up-to-date, and respects the org boundary automatically."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy import Text, desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from adhkar.api.deps import (
    CurrentUser,
    get_db,
    require_current_org,
    require_permission,
)
from adhkar.db.models import AuditLog, Case

router = APIRouter(tags=["cases"])


class TimelineEntry(BaseModel):
    id: UUID
    action: str
    entity_type: str
    entity_id: UUID | None
    actor_user_id: UUID | None
    created_at: datetime
    diff: dict[str, Any]


class TimelineResponse(BaseModel):
    case_id: UUID
    entries: list[TimelineEntry]


@router.get("/v1/cases/{case_id}/timeline", response_model=TimelineResponse)
async def case_timeline(
    case_id: UUID,
    _user: Annotated[CurrentUser, Depends(require_permission("viewCase"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 200,
) -> TimelineResponse:
    safe_limit = max(1, min(500, int(limit)))
    case = (
        await db.execute(
            select(Case).where(
                Case.id == case_id,
                Case.organization_id == org_id,
                Case.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if case is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "case_not_found")
    # Match either:
    #  - direct (entity_type='case' AND entity_id=case_id)
    #  - cross-link (diff JSON contains the case_id text — covers
    #    alert.promoted events that store case_id in their diff)
    case_id_str = str(case_id)
    stmt = (
        select(AuditLog)
        .where(
            AuditLog.organization_id == org_id,
            or_(
                (AuditLog.entity_type == "case") & (AuditLog.entity_id == case_id),
                AuditLog.diff.cast(Text).contains(case_id_str),
            ),
        )
        .order_by(desc(AuditLog.created_at))
        .limit(safe_limit)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return TimelineResponse(
        case_id=case_id,
        entries=[
            TimelineEntry(
                id=r.id,
                action=r.action,
                entity_type=r.entity_type,
                entity_id=r.entity_id,
                actor_user_id=r.actor_user_id,
                created_at=r.created_at,
                diff=r.diff or {},
            )
            for r in rows
        ],
    )


class CaseReport(BaseModel):
    case_id: UUID
    title: str
    number: int
    severity: int
    tlp: str
    stage: str
    description: str | None
    resolution: str | None
    tags: list[str]
    pages: list[dict[str, str]]
    markdown: str


@router.get("/v1/cases/{case_id}/report", response_model=CaseReport)
async def case_report(
    case_id: UUID,
    _user: Annotated[CurrentUser, Depends(require_permission("viewCase"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CaseReport:
    """Bundle case header + all case_pages into a single markdown report.

    Returns the structured fields PLUS a concatenated markdown blob that
    the UI can hand to the user's PDF print dialog or pass through a
    server-side markdown→PDF pipeline (out of scope here)."""
    from adhkar.db.models import CasePage

    case = (
        await db.execute(
            select(Case).where(
                Case.id == case_id,
                Case.organization_id == org_id,
                Case.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if case is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "case_not_found")
    pages = (
        (
            await db.execute(
                select(CasePage)
                .where(CasePage.case_id == case_id, CasePage.organization_id == org_id)
                .order_by(CasePage.title)
            )
        )
        .scalars()
        .all()
    )
    parts = [
        f"# #{case.number} {case.title}",
        "",
        f"- **Severity:** {case.severity}",
        f"- **TLP:** {case.tlp}",
        f"- **PAP:** {case.pap}",
        f"- **Stage:** {case.stage}",
        f"- **Status:** {case.status}",
        f"- **Tags:** {', '.join(case.tags) or '(none)'}",
        "",
    ]
    if case.description:
        parts += ["## Description", "", case.description, ""]
    if case.resolution:
        parts += ["## Resolution", "", case.resolution, ""]
    for p in pages:
        parts += [f"## {p.title}", "", p.content or "_(empty)_", ""]
    markdown = "\n".join(parts)
    return CaseReport(
        case_id=case.id,
        title=case.title,
        number=case.number,
        severity=case.severity,
        tlp=case.tlp,
        stage=case.stage,
        description=case.description,
        resolution=case.resolution,
        tags=list(case.tags),
        pages=[{"slug": p.slug, "title": p.title, "content": p.content} for p in pages],
        markdown=markdown,
    )


@router.get(
    "/v1/cases/{case_id}/report.html",
    response_class=HTMLResponse,
    responses={200: {"content": {"text/html": {}}}},
)
async def case_report_html(
    case_id: UUID,
    user: Annotated[CurrentUser, Depends(require_permission("viewCase"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> HTMLResponse:
    """Server-rendered HTML wrapper around the case report markdown.

    Wraps the markdown in a print-friendly stylesheet so 'Save as PDF'
    from any browser produces a clean handoff doc — no external PDF dep."""
    import markdown as md  # type: ignore[import-untyped]

    report = await case_report(case_id=case_id, _user=user, org_id=org_id, db=db)
    body_html = md.markdown(
        report.markdown,
        extensions=["fenced_code", "tables"],
    )
    css = (
        "body{font:14px -apple-system,Segoe UI,sans-serif;"
        "max-width:780px;margin:2rem auto;padding:0 1rem;color:#1f2937}"
        "h1{font-size:24px;border-bottom:1px solid #e5e7eb;padding-bottom:.5rem}"
        "h2{font-size:18px;margin-top:1.5rem;color:#374151}"
        "pre{background:#f3f4f6;padding:.75rem;border-radius:.25rem;overflow:auto}"
        "code{background:#f3f4f6;padding:0 .25rem;border-radius:.125rem}"
        "table{border-collapse:collapse;width:100%}"
        "th,td{border:1px solid #e5e7eb;padding:.4rem .6rem;text-align:left}"
        "@media print{body{margin:0;max-width:none}}"
    )
    html = (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>Adhkar IR · Case #{report.number}</title>"
        f"<style>{css}</style></head><body>{body_html}</body></html>"
    )
    return HTMLResponse(content=html)
