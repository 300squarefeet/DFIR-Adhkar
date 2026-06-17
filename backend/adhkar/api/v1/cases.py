"""Case CRUD + Task CRUD endpoints (Phase 3)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from adhkar.api.deps import (
    CurrentUser,
    get_db,
    require_current_org,
    require_permission,
)
from adhkar.audit import audit_and_emit
from adhkar.db.models import Case, Task, TaskLog
from adhkar.db.repositories.cases import CaseRepository

router = APIRouter(tags=["cases"])

TLP = Literal["white", "green", "amber", "amber-strict", "red"]
PAP = Literal["white", "green", "amber", "red"]
STAGE = Literal["open", "in_progress", "closed"]
TASK_STATUS = Literal["Waiting", "InProgress", "Completed", "Cancelled"]


class CaseDTO(BaseModel):
    id: UUID
    organization_id: UUID
    number: int
    title: str
    description: str | None
    severity: int
    tlp: str
    pap: str
    status: str
    stage: str
    resolution: str | None
    impact_summary: str | None
    assignee_id: UUID | None
    start_date: datetime | None
    end_date: datetime | None
    tags: list[str]
    custom_fields: dict[str, Any]
    flagged: bool
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime


class CaseCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    description: str | None = None
    severity: int = Field(default=2, ge=1, le=4)
    tlp: TLP = "amber"
    pap: PAP = "amber"
    status: str = "Open"
    stage: STAGE = "open"
    assignee_id: UUID | None = None
    tags: list[str] = []
    custom_fields: dict[str, Any] = {}
    flagged: bool = False
    start_date: datetime | None = None


class CasePatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = None
    severity: int | None = Field(default=None, ge=1, le=4)
    tlp: TLP | None = None
    pap: PAP | None = None
    status: str | None = None
    stage: STAGE | None = None
    resolution: str | None = None
    impact_summary: str | None = None
    assignee_id: UUID | None = None
    tags: list[str] | None = None
    custom_fields: dict[str, Any] | None = None
    flagged: bool | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None


def _case_to_dto(c: Case) -> CaseDTO:
    return CaseDTO(
        id=c.id,
        organization_id=c.organization_id,
        number=c.number,
        title=c.title,
        description=c.description,
        severity=c.severity,
        tlp=c.tlp,
        pap=c.pap,
        status=c.status,
        stage=c.stage,
        resolution=c.resolution,
        impact_summary=c.impact_summary,
        assignee_id=c.assignee_id,
        start_date=c.start_date,
        end_date=c.end_date,
        tags=list(c.tags),
        custom_fields=dict(c.custom_fields),
        flagged=c.flagged,
        created_by=c.created_by,
        created_at=c.created_at,
        updated_at=c.updated_at,
    )


@router.get("/v1/cases", response_model=list[CaseDTO])
async def list_cases(
    _user: Annotated[CurrentUser, Depends(require_permission("viewCase"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
    stage: STAGE | None = None,
    assignee_id: UUID | None = None,
    severity: int | None = None,
    tag: str | None = None,
    flagged: bool | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    updated_since: datetime | None = None,
    limit: int = 100,
) -> list[CaseDTO]:
    """Case list. `since`/`until` bound created_at; `updated_since=<ISO>`
    is a delta-sync companion that bounds updated_at and switches the
    sort to updated_at DESC — symmetric with RC172/RC174."""
    stmt = select(Case).where(Case.organization_id == org_id, Case.deleted_at.is_(None))
    if stage:
        stmt = stmt.where(Case.stage == stage)
    if assignee_id:
        stmt = stmt.where(Case.assignee_id == assignee_id)
    if severity is not None:
        stmt = stmt.where(Case.severity == severity)
    if tag:
        stmt = stmt.where(Case.tags.contains([tag]))
    if flagged is not None:
        stmt = stmt.where(Case.flagged == flagged)
    if since is not None:
        stmt = stmt.where(Case.created_at >= since)
    if until is not None:
        stmt = stmt.where(Case.created_at < until)
    if updated_since is not None:
        stmt = stmt.where(Case.updated_at >= updated_since).order_by(Case.updated_at.desc())
    else:
        stmt = stmt.order_by(Case.number.desc())
    stmt = stmt.limit(limit)
    rows = (await db.execute(stmt)).scalars().all()
    return [_case_to_dto(c) for c in rows]


@router.get("/v1/cases/recent", response_model=list[CaseDTO])
async def list_recent_cases(
    user: Annotated[CurrentUser, Depends(require_permission("viewCase"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 10,
    assignee_id: UUID | None = None,
    mine: bool | None = None,
    stage: str | None = None,
    open_only: bool | None = None,
    tag: str | None = None,
) -> list[CaseDTO]:
    """N most-recently-updated cases (`updated_at` DESC) for the current
    org, default 10, capped 50. `mine=true` is shorthand for
    `assignee_id=<current user>`. `stage=<name>` filters to one workflow
    stage (open, in_progress, etc). `open_only=true` shorthand excludes
    `stage=closed`. `tag=<name>` keeps only cases whose tags array
    contains that exact tag. Skips soft-deleted cases. Same DTO shape
    as the main list endpoint so the frontend can reuse the renderer."""
    safe_limit = max(1, min(50, int(limit)))
    stmt = (
        select(Case)
        .where(Case.organization_id == org_id, Case.deleted_at.is_(None))
        .order_by(Case.updated_at.desc())
        .limit(safe_limit)
    )
    if mine is True:
        stmt = stmt.where(Case.assignee_id == user.user_id)
    elif assignee_id is not None:
        stmt = stmt.where(Case.assignee_id == assignee_id)
    if stage is not None:
        stmt = stmt.where(Case.stage == stage)
    elif open_only is True:
        stmt = stmt.where(Case.stage != "closed")
    if tag is not None:
        stmt = stmt.where(Case.tags.contains([tag]))
    rows = (await db.execute(stmt)).scalars().all()
    return [_case_to_dto(c) for c in rows]


class ContributorRow(BaseModel):
    user_id: UUID
    comment_count: int
    task_log_count: int
    audit_count: int


@router.get("/v1/cases/{case_id}/contributors", response_model=list[ContributorRow])
async def list_case_contributors(
    case_id: UUID,
    _user: Annotated[CurrentUser, Depends(require_permission("viewCase"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
    since: datetime | None = None,
) -> list[ContributorRow]:
    """Distinct user_ids that have touched this case via Comments, TaskLogs,
    or AuditLog entries scoped to the case. Excludes None/system actors.
    Ordered by total activity (comments+logs+audit) desc. Optional
    `since=<ISO>` scopes all three aggregations to the trailing window
    so a "recent collaborators" badge can hit one URL."""
    # Fail-fast 404 if the case doesn't exist or isn't in caller's org.
    from adhkar.db.models import AuditLog as _AuditLog
    from adhkar.db.models import Comment as _Comment
    from adhkar.db.models import TaskLog as _TaskLog

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

    # Run three small aggregations in parallel-ish via sequential awaits;
    # each is a small grouped count.
    comment_stmt = (
        select(_Comment.author_id, func.count().label("n"))
        .where(_Comment.case_id == case_id, _Comment.author_id.is_not(None))
        .group_by(_Comment.author_id)
    )
    if since is not None:
        comment_stmt = comment_stmt.where(_Comment.created_at >= since)
    comment_rows = (await db.execute(comment_stmt)).all()
    tasklog_stmt = (
        select(_TaskLog.author_id, func.count().label("n"))
        .join(Task, Task.id == _TaskLog.task_id)
        .where(Task.case_id == case_id, _TaskLog.author_id.is_not(None))
        .group_by(_TaskLog.author_id)
    )
    if since is not None:
        tasklog_stmt = tasklog_stmt.where(_TaskLog.created_at >= since)
    tasklog_rows = (await db.execute(tasklog_stmt)).all()
    audit_stmt = (
        select(_AuditLog.actor_user_id, func.count().label("n"))
        .where(
            _AuditLog.organization_id == org_id,
            _AuditLog.entity_type == "case",
            _AuditLog.entity_id == case_id,
            _AuditLog.actor_user_id.is_not(None),
        )
        .group_by(_AuditLog.actor_user_id)
    )
    if since is not None:
        audit_stmt = audit_stmt.where(_AuditLog.created_at >= since)
    audit_rows = (await db.execute(audit_stmt)).all()

    per_user: dict[UUID, dict[str, int]] = {}
    for uid, n in comment_rows:
        per_user.setdefault(uid, {"comment": 0, "task_log": 0, "audit": 0})["comment"] = int(n)
    for uid, n in tasklog_rows:
        per_user.setdefault(uid, {"comment": 0, "task_log": 0, "audit": 0})["task_log"] = int(n)
    for uid, n in audit_rows:
        per_user.setdefault(uid, {"comment": 0, "task_log": 0, "audit": 0})["audit"] = int(n)

    out = [
        ContributorRow(
            user_id=uid,
            comment_count=v["comment"],
            task_log_count=v["task_log"],
            audit_count=v["audit"],
        )
        for uid, v in per_user.items()
    ]
    out.sort(key=lambda r: -(r.comment_count + r.task_log_count + r.audit_count))
    return out


@router.get("/v1/cases/{case_id}/contributors/me", response_model=ContributorRow)
async def my_case_contributor_row(
    case_id: UUID,
    user: Annotated[CurrentUser, Depends(require_permission("viewCase"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ContributorRow:
    """The caller's own activity counts on this case (comments, task_log,
    audit). Returns zeros if the caller has never touched the case
    instead of 404, so a "your activity" badge can render unconditionally."""
    from adhkar.db.models import AuditLog as _AuditLog
    from adhkar.db.models import Comment as _Comment
    from adhkar.db.models import TaskLog as _TaskLog

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
    comments_n = int(
        (
            await db.execute(
                select(func.count())
                .select_from(_Comment)
                .where(_Comment.case_id == case_id, _Comment.author_id == user.user_id)
            )
        ).scalar_one()
    )
    task_logs_n = int(
        (
            await db.execute(
                select(func.count())
                .select_from(_TaskLog)
                .join(Task, Task.id == _TaskLog.task_id)
                .where(Task.case_id == case_id, _TaskLog.author_id == user.user_id)
            )
        ).scalar_one()
    )
    audit_n = int(
        (
            await db.execute(
                select(func.count())
                .select_from(_AuditLog)
                .where(
                    _AuditLog.organization_id == org_id,
                    _AuditLog.entity_type == "case",
                    _AuditLog.entity_id == case_id,
                    _AuditLog.actor_user_id == user.user_id,
                )
            )
        ).scalar_one()
    )
    return ContributorRow(
        user_id=user.user_id,
        comment_count=comments_n,
        task_log_count=task_logs_n,
        audit_count=audit_n,
    )


class RelatedCaseRow(BaseModel):
    case_id: UUID
    number: int
    title: str
    severity: int
    stage: str
    relation: str


@router.get("/v1/cases/{case_id}/related", response_model=list[RelatedCaseRow])
async def list_related_cases(
    case_id: UUID,
    _user: Annotated[CurrentUser, Depends(require_permission("viewCase"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
    relation: str | None = None,
    stage: str | None = None,
    open_only: bool | None = None,
) -> list[RelatedCaseRow]:
    """Cases linked to this one via CaseLink in either direction. Returns
    the relation as recorded on the link (related/duplicate/child_of/
    caused_by/references). Excludes soft-deleted and de-duplicates if a
    case is linked twice. Optional `relation=<value>` keeps only links
    of that type; `stage=<name>` scopes to one workflow stage and
    `open_only=true` excludes closed peers."""
    from adhkar.db.models import CaseLink as _CaseLink

    # Confirm the source case is in caller's org first (404 otherwise).
    src = (
        await db.execute(
            select(Case).where(
                Case.id == case_id,
                Case.organization_id == org_id,
                Case.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if src is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "case_not_found")
    link_stmt = select(_CaseLink).where(
        _CaseLink.organization_id == org_id,
        or_(
            _CaseLink.source_case_id == case_id,
            _CaseLink.target_case_id == case_id,
        ),
    )
    if relation is not None:
        link_stmt = link_stmt.where(_CaseLink.relation == relation)
    rows = (await db.execute(link_stmt)).scalars().all()
    other_ids: dict[UUID, str] = {}
    for link in rows:
        peer = link.target_case_id if link.source_case_id == case_id else link.source_case_id
        # First-seen relation wins if a case is linked twice.
        other_ids.setdefault(peer, link.relation)
    if not other_ids:
        return []
    peer_stmt = select(Case).where(
        Case.id.in_(list(other_ids.keys())),
        Case.organization_id == org_id,
        Case.deleted_at.is_(None),
    )
    if stage is not None:
        peer_stmt = peer_stmt.where(Case.stage == stage)
    elif open_only is True:
        peer_stmt = peer_stmt.where(Case.stage != "closed")
    peers = (await db.execute(peer_stmt)).scalars().all()
    return [
        RelatedCaseRow(
            case_id=c.id,
            number=c.number,
            title=c.title,
            severity=c.severity,
            stage=c.stage,
            relation=other_ids[c.id],
        )
        for c in peers
    ]


class BulkPatchPayload(BaseModel):
    ids: list[UUID] = Field(min_length=1, max_length=200)
    patch: CasePatch


class BulkPatchResult(BaseModel):
    updated: int
    ids: list[UUID]


@router.post("/v1/cases/bulk-patch", response_model=BulkPatchResult)
async def bulk_patch_cases(
    body: BulkPatchPayload,
    user: Annotated[CurrentUser, Depends(require_permission("manageCase"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> BulkPatchResult:
    """Apply the same patch to a list of cases. Same field validation as the
    single-case PATCH; rows outside the caller's org are silently dropped."""
    patch = body.patch.model_dump(exclude_unset=True)
    if not patch:
        return BulkPatchResult(updated=0, ids=[])
    rows = (
        (
            await db.execute(
                select(Case).where(
                    Case.organization_id == org_id,
                    Case.id.in_(body.ids),
                    Case.deleted_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    updated_ids: list[UUID] = []
    auto_close = patch.get("stage") == "closed" and "end_date" not in patch
    for c in rows:
        for field, value in patch.items():
            setattr(c, field, value)
        if auto_close and c.end_date is None:
            c.end_date = datetime.now(tz=UTC)
        updated_ids.append(c.id)
    await db.flush()
    for cid in updated_ids:
        await audit_and_emit(
            db,
            actor_user_id=user.user_id,
            organization_id=org_id,
            action="bulk_updated",
            entity_type="case",
            entity_id=cid,
            diff={k: str(v) for k, v in patch.items()},
        )
    return BulkPatchResult(updated=len(updated_ids), ids=updated_ids)


@router.post("/v1/cases", response_model=CaseDTO, status_code=status.HTTP_201_CREATED)
async def create_case(
    body: CaseCreate,
    user: Annotated[CurrentUser, Depends(require_permission("manageCase"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CaseDTO:
    repo = CaseRepository(db, org_id)
    # Retry on unique(organization_id, number) race up to 3 times.
    for _ in range(3):
        number = await repo.next_number()
        case = Case(
            organization_id=org_id,
            number=number,
            title=body.title,
            description=body.description,
            severity=body.severity,
            tlp=body.tlp,
            pap=body.pap,
            status=body.status,
            stage=body.stage,
            assignee_id=body.assignee_id,
            tags=body.tags,
            custom_fields=body.custom_fields,
            flagged=body.flagged,
            start_date=body.start_date,
            created_by=user.user_id,
        )
        db.add(case)
        try:
            await db.flush()
        except IntegrityError:
            await db.rollback()
            continue
        await audit_and_emit(
            db,
            actor_user_id=user.user_id,
            organization_id=org_id,
            action="created",
            entity_type="case",
            entity_id=case.id,
            diff={"number": case.number, "title": case.title, "severity": case.severity},
        )
        return _case_to_dto(case)
    raise HTTPException(status.HTTP_409_CONFLICT, "case_number_assignment_failed")


@router.get(
    "/v1/tasks/export-csv",
    response_class=PlainTextResponse,
    responses={200: {"content": {"text/csv": {}}}},
)
async def export_tasks_csv(
    user: Annotated[CurrentUser, Depends(require_permission("viewTask"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
    assignee_id: UUID | None = None,
    status_filter: TASK_STATUS | None = None,
    mandatory: bool | None = None,
    overdue: bool | None = None,
    mine: bool | None = None,
    due_within_days: int | None = None,
    updated_since: datetime | None = None,
) -> PlainTextResponse:
    """CSV dump matching GET /v1/tasks filter surface (including RC166
    due_within_days and RC176 updated_since)."""
    import csv
    import io

    stmt = select(Task).where(Task.organization_id == org_id)
    if mine is True:
        stmt = stmt.where(Task.assignee_id == user.user_id)
    elif assignee_id:
        stmt = stmt.where(Task.assignee_id == assignee_id)
    if status_filter:
        stmt = stmt.where(Task.status == status_filter)
    if mandatory is not None:
        stmt = stmt.where(Task.mandatory == mandatory)
    if overdue is True:
        stmt = stmt.where(
            Task.due_date.is_not(None),
            Task.due_date < datetime.now(tz=UTC),
            Task.status.notin_(("Completed", "Cancelled")),
        )
    if due_within_days is not None:
        bounded = max(1, min(90, int(due_within_days)))
        now = datetime.now(tz=UTC)
        horizon = now + timedelta(days=bounded)
        stmt = stmt.where(
            Task.due_date.is_not(None),
            Task.due_date >= now,
            Task.due_date <= horizon,
            Task.status.notin_(("Completed", "Cancelled")),
        )
    if updated_since is not None:
        stmt = stmt.where(Task.updated_at >= updated_since)
    stmt = stmt.order_by(Task.due_date.asc().nulls_last(), Task.created_at.desc())
    rows = (await db.execute(stmt)).scalars().all()
    buf = io.StringIO()
    w = csv.writer(buf, quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
    w.writerow(
        [
            "case_id",
            "title",
            "status",
            "assignee_id",
            "due_date",
            "mandatory",
            "group",
            "created_at",
        ]
    )
    for t in rows:
        w.writerow(
            [
                str(t.case_id),
                t.title,
                t.status,
                str(t.assignee_id) if t.assignee_id else "",
                t.due_date.isoformat() if t.due_date else "",
                "true" if t.mandatory else "false",
                t.group or "",
                t.created_at.isoformat(),
            ]
        )
    return PlainTextResponse(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="adhkar-tasks.csv"'},
    )


@router.get(
    "/v1/cases/export-csv",
    response_class=PlainTextResponse,
    responses={200: {"content": {"text/csv": {}}}},
)
async def export_cases_csv(
    _user: Annotated[CurrentUser, Depends(require_permission("viewCase"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
    stage: STAGE | None = None,
    severity: int | None = None,
    flagged: bool | None = None,
    tag: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    updated_since: datetime | None = None,
) -> PlainTextResponse:
    """CSV dump of cases. Same filter surface as the list endpoint
    (including RC175 updated_since)."""
    import csv
    import io

    stmt = select(Case).where(Case.organization_id == org_id, Case.deleted_at.is_(None))
    if stage:
        stmt = stmt.where(Case.stage == stage)
    if severity is not None:
        stmt = stmt.where(Case.severity == severity)
    if flagged is not None:
        stmt = stmt.where(Case.flagged == flagged)
    if tag:
        stmt = stmt.where(Case.tags.contains([tag]))
    if since is not None:
        stmt = stmt.where(Case.created_at >= since)
    if until is not None:
        stmt = stmt.where(Case.created_at < until)
    if updated_since is not None:
        stmt = stmt.where(Case.updated_at >= updated_since)
    rows = (await db.execute(stmt.order_by(Case.number.desc()))).scalars().all()
    buf = io.StringIO()
    w = csv.writer(buf, quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
    w.writerow(
        [
            "number",
            "title",
            "severity",
            "tlp",
            "pap",
            "status",
            "stage",
            "assignee_id",
            "flagged",
            "tags",
            "created_at",
            "end_date",
        ]
    )
    for c in rows:
        w.writerow(
            [
                c.number,
                c.title,
                c.severity,
                c.tlp,
                c.pap,
                c.status,
                c.stage,
                str(c.assignee_id) if c.assignee_id else "",
                "true" if c.flagged else "false",
                ",".join(c.tags),
                c.created_at.isoformat(),
                c.end_date.isoformat() if c.end_date else "",
            ]
        )
    return PlainTextResponse(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="adhkar-cases.csv"'},
    )


@router.get("/v1/cases/{case_id}", response_model=CaseDTO)
async def get_case(
    case_id: UUID,
    _user: Annotated[CurrentUser, Depends(require_permission("viewCase"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CaseDTO:
    repo = CaseRepository(db, org_id)
    c = await repo.get(case_id)
    if not c or c.deleted_at:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "case_not_found")
    return _case_to_dto(c)


@router.patch("/v1/cases/{case_id}", response_model=CaseDTO)
async def patch_case(
    case_id: UUID,
    body: CasePatch,
    user: Annotated[CurrentUser, Depends(require_permission("manageCase"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CaseDTO:
    repo = CaseRepository(db, org_id)
    c = await repo.get(case_id)
    if not c or c.deleted_at:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "case_not_found")
    patch = body.model_dump(exclude_unset=True)
    if patch.get("stage") == "closed" and c.end_date is None and "end_date" not in patch:
        c.end_date = datetime.now(tz=UTC)
    for field, value in patch.items():
        setattr(c, field, value)
    await db.flush()
    await audit_and_emit(
        db,
        actor_user_id=user.user_id,
        organization_id=org_id,
        action="updated",
        entity_type="case",
        entity_id=c.id,
        diff={k: str(v) for k, v in patch.items()},
    )
    return _case_to_dto(c)


@router.delete("/v1/cases/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_case(
    case_id: UUID,
    user: Annotated[CurrentUser, Depends(require_permission("manageCase"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    repo = CaseRepository(db, org_id)
    c = await repo.get(case_id)
    if not c or c.deleted_at:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "case_not_found")
    c.deleted_at = datetime.now(tz=UTC)
    await db.flush()
    await audit_and_emit(
        db,
        actor_user_id=user.user_id,
        organization_id=org_id,
        action="deleted",
        entity_type="case",
        entity_id=c.id,
    )


# ---------- Tasks ----------


class TaskDTO(BaseModel):
    id: UUID
    case_id: UUID
    title: str
    group: str | None
    description: str | None
    status: str
    assignee_id: UUID | None
    due_date: datetime | None
    order_index: int
    mandatory: bool
    created_at: datetime
    updated_at: datetime


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    group: str | None = None
    description: str | None = None
    status: TASK_STATUS = "Waiting"
    assignee_id: UUID | None = None
    due_date: datetime | None = None
    order_index: int = 0
    mandatory: bool = False


class TaskPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    group: str | None = None
    description: str | None = None
    status: TASK_STATUS | None = None
    assignee_id: UUID | None = None
    due_date: datetime | None = None
    order_index: int | None = None
    mandatory: bool | None = None


def _task_to_dto(t: Task) -> TaskDTO:
    return TaskDTO(
        id=t.id,
        case_id=t.case_id,
        title=t.title,
        group=t.group,
        description=t.description,
        status=t.status,
        assignee_id=t.assignee_id,
        due_date=t.due_date,
        order_index=t.order_index,
        mandatory=t.mandatory,
        created_at=t.created_at,
        updated_at=t.updated_at,
    )


async def _load_case_or_404(db: AsyncSession, org_id: UUID, case_id: UUID) -> Case:
    c = (
        await db.execute(
            select(Case).where(
                Case.id == case_id, Case.organization_id == org_id, Case.deleted_at.is_(None)
            )
        )
    ).scalar_one_or_none()
    if not c:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "case_not_found")
    return c


@router.get("/v1/tasks/recent", response_model=list[TaskDTO])
async def list_recent_tasks(
    user: Annotated[CurrentUser, Depends(require_permission("viewTask"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 10,
    mine: bool | None = None,
    status_filter: TASK_STATUS | None = None,
    open_only: bool | None = None,
) -> list[TaskDTO]:
    """N most-recently-updated tasks (`updated_at` DESC), default 10, cap
    50. `mine=true` is shorthand for assignee_id=<current user>.
    `status_filter=<value>` scopes to one task status; `open_only=true`
    excludes Completed and Cancelled. Mirrors /v1/cases/recent for
    dashboard symmetry."""
    safe_limit = max(1, min(50, int(limit)))
    stmt = (
        select(Task)
        .where(Task.organization_id == org_id)
        .order_by(Task.updated_at.desc())
        .limit(safe_limit)
    )
    if mine is True:
        stmt = stmt.where(Task.assignee_id == user.user_id)
    if status_filter is not None:
        stmt = stmt.where(Task.status == status_filter)
    elif open_only is True:
        stmt = stmt.where(Task.status.notin_(("Completed", "Cancelled")))
    rows = (await db.execute(stmt)).scalars().all()
    return [_task_to_dto(t) for t in rows]


@router.get("/v1/tasks", response_model=list[TaskDTO])
async def list_all_tasks(
    user: Annotated[CurrentUser, Depends(require_permission("viewTask"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
    assignee_id: UUID | None = None,
    status_filter: TASK_STATUS | None = None,
    mandatory: bool | None = None,
    overdue: bool | None = None,
    mine: bool | None = None,
    due_within_days: int | None = None,
    updated_since: datetime | None = None,
    limit: int = 200,
) -> list[TaskDTO]:
    """Cross-case task list. Used by the analyst's 'my queue' view.

    `mine=true` is shorthand for assignee_id=<current user>. `overdue=true`
    keeps only rows whose due_date is in the past AND whose status is not
    Completed/Cancelled. `due_within_days=N` (1..90) keeps only rows with
    a due_date inside the next N days that aren't already
    Completed/Cancelled. `updated_since=<ISO>` bounds Task.updated_at and
    switches the sort to updated_at DESC — completes the delta-sync trio
    with RC172/RC174/RC175."""
    safe_limit = max(1, min(500, int(limit)))
    stmt = select(Task).where(Task.organization_id == org_id)
    if mine is True:
        stmt = stmt.where(Task.assignee_id == user.user_id)
    elif assignee_id:
        stmt = stmt.where(Task.assignee_id == assignee_id)
    if status_filter:
        stmt = stmt.where(Task.status == status_filter)
    if mandatory is not None:
        stmt = stmt.where(Task.mandatory == mandatory)
    if overdue is True:
        stmt = stmt.where(
            Task.due_date.is_not(None),
            Task.due_date < datetime.now(tz=UTC),
            Task.status.notin_(("Completed", "Cancelled")),
        )
    if due_within_days is not None:
        bounded = max(1, min(90, int(due_within_days)))
        now = datetime.now(tz=UTC)
        horizon = now + timedelta(days=bounded)
        stmt = stmt.where(
            Task.due_date.is_not(None),
            Task.due_date >= now,
            Task.due_date <= horizon,
            Task.status.notin_(("Completed", "Cancelled")),
        )
    if updated_since is not None:
        stmt = stmt.where(Task.updated_at >= updated_since).order_by(Task.updated_at.desc())
    else:
        stmt = stmt.order_by(Task.due_date.asc().nulls_last(), Task.created_at.desc())
    stmt = stmt.limit(safe_limit)
    rows = (await db.execute(stmt)).scalars().all()
    return [_task_to_dto(t) for t in rows]


@router.get("/v1/cases/{case_id}/tasks", response_model=list[TaskDTO])
async def list_tasks(
    case_id: UUID,
    _user: Annotated[CurrentUser, Depends(require_permission("viewTask"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
    status_filter: TASK_STATUS | None = None,
    open_only: bool | None = None,
    mandatory: bool | None = None,
) -> list[TaskDTO]:
    """Per-case task list, board order. `status_filter=<value>` scopes
    to one status; `open_only=true` excludes Completed and Cancelled;
    `mandatory=true|false` filters the required-flag — same filter
    surface as the cross-case list endpoint so a re-fetch shares
    code paths."""
    await _load_case_or_404(db, org_id, case_id)
    stmt = (
        select(Task)
        .where(Task.case_id == case_id, Task.organization_id == org_id)
        .order_by(Task.order_index, Task.created_at)
    )
    if status_filter is not None:
        stmt = stmt.where(Task.status == status_filter)
    elif open_only is True:
        stmt = stmt.where(Task.status.notin_(("Completed", "Cancelled")))
    if mandatory is not None:
        stmt = stmt.where(Task.mandatory == mandatory)
    rows = (await db.execute(stmt)).scalars().all()
    return [_task_to_dto(t) for t in rows]


class TaskStatusBucket(BaseModel):
    status: str
    count: int


class CaseTasksSummaryResponse(BaseModel):
    case_id: UUID
    total: int
    by_status: list[TaskStatusBucket]


@router.get(
    "/v1/cases/{case_id}/tasks/summary",
    response_model=CaseTasksSummaryResponse,
)
async def case_tasks_summary(
    case_id: UUID,
    _user: Annotated[CurrentUser, Depends(require_permission("viewTask"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CaseTasksSummaryResponse:
    """Per-status task count for this case, zero-filled over the four
    canonical statuses so a progress bar can render without empty-bucket
    quirks."""
    await _load_case_or_404(db, org_id, case_id)
    rows = (
        await db.execute(
            select(Task.status, func.count().label("n"))
            .where(Task.case_id == case_id, Task.organization_id == org_id)
            .group_by(Task.status)
        )
    ).all()
    by_status: dict[str, int] = {str(r[0]): int(r[1]) for r in rows}
    canonical = ("Waiting", "InProgress", "Completed", "Cancelled")
    buckets = [TaskStatusBucket(status=s, count=by_status.get(s, 0)) for s in canonical]
    return CaseTasksSummaryResponse(
        case_id=case_id,
        total=sum(b.count for b in buckets),
        by_status=buckets,
    )


@router.post(
    "/v1/cases/{case_id}/tasks", response_model=TaskDTO, status_code=status.HTTP_201_CREATED
)
async def create_task(
    case_id: UUID,
    body: TaskCreate,
    _user: Annotated[CurrentUser, Depends(require_permission("manageTask"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TaskDTO:
    await _load_case_or_404(db, org_id, case_id)
    task = Task(
        organization_id=org_id,
        case_id=case_id,
        title=body.title,
        group=body.group,
        description=body.description,
        status=body.status,
        assignee_id=body.assignee_id,
        due_date=body.due_date,
        order_index=body.order_index,
        mandatory=body.mandatory,
    )
    db.add(task)
    await db.flush()
    return _task_to_dto(task)


class TaskReorder(BaseModel):
    ordered_ids: list[UUID] = Field(min_length=1, max_length=500)


class TaskReorderResult(BaseModel):
    updated: int


@router.post("/v1/cases/{case_id}/tasks/reorder", response_model=TaskReorderResult)
async def reorder_tasks(
    case_id: UUID,
    body: TaskReorder,
    user: Annotated[CurrentUser, Depends(require_permission("manageTask"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TaskReorderResult:
    """Assign each task in `ordered_ids` an ascending order_index by
    position. Tasks belonging to other cases or orgs are silently
    skipped; missing ids in the list keep their old position."""
    await _load_case_or_404(db, org_id, case_id)
    rows = (
        (
            await db.execute(
                select(Task).where(
                    Task.case_id == case_id,
                    Task.organization_id == org_id,
                    Task.id.in_(body.ordered_ids),
                )
            )
        )
        .scalars()
        .all()
    )
    by_id = {t.id: t for t in rows}
    updated = 0
    for position, tid in enumerate(body.ordered_ids):
        t = by_id.get(tid)
        if t is None:
            continue
        if t.order_index != position:
            t.order_index = position
            updated += 1
    await db.flush()
    if updated:
        await audit_and_emit(
            db,
            actor_user_id=user.user_id,
            organization_id=org_id,
            action="reordered_tasks",
            entity_type="case",
            entity_id=case_id,
            diff={"ordered_ids": [str(i) for i in body.ordered_ids]},
        )
    return TaskReorderResult(updated=updated)


@router.patch("/v1/tasks/{task_id}", response_model=TaskDTO)
async def patch_task(
    task_id: UUID,
    body: TaskPatch,
    _user: Annotated[CurrentUser, Depends(require_permission("manageTask"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TaskDTO:
    t = (
        await db.execute(select(Task).where(Task.id == task_id, Task.organization_id == org_id))
    ).scalar_one_or_none()
    if not t:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "task_not_found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(t, field, value)
    await db.flush()
    return _task_to_dto(t)


class BulkTaskPatchPayload(BaseModel):
    ids: list[UUID] = Field(min_length=1, max_length=200)
    patch: TaskPatch


@router.post("/v1/tasks/bulk-patch", response_model=BulkPatchResult)
async def bulk_patch_tasks(
    body: BulkTaskPatchPayload,
    user: Annotated[CurrentUser, Depends(require_permission("manageTask"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> BulkPatchResult:
    """Apply the same TaskPatch to up to 200 tasks. Rows outside the
    caller's org are silently dropped. One audit row per id."""
    patch = body.patch.model_dump(exclude_unset=True)
    if not patch:
        return BulkPatchResult(updated=0, ids=[])
    rows = (
        (
            await db.execute(
                select(Task).where(
                    Task.organization_id == org_id,
                    Task.id.in_(body.ids),
                )
            )
        )
        .scalars()
        .all()
    )
    updated_ids: list[UUID] = []
    for t in rows:
        for field, value in patch.items():
            setattr(t, field, value)
        updated_ids.append(t.id)
    await db.flush()
    for tid in updated_ids:
        await audit_and_emit(
            db,
            actor_user_id=user.user_id,
            organization_id=org_id,
            action="bulk_updated",
            entity_type="task",
            entity_id=tid,
            diff={k: str(v) for k, v in patch.items()},
        )
    return BulkPatchResult(updated=len(updated_ids), ids=updated_ids)


@router.delete("/v1/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: UUID,
    _user: Annotated[CurrentUser, Depends(require_permission("manageTask"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    t = (
        await db.execute(select(Task).where(Task.id == task_id, Task.organization_id == org_id))
    ).scalar_one_or_none()
    if not t:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "task_not_found")
    await db.delete(t)
    await db.flush()


# ---------- Task logs ----------


class TaskLogDTO(BaseModel):
    id: UUID
    task_id: UUID
    author_id: UUID | None
    content: str
    created_at: datetime


class TaskLogCreate(BaseModel):
    content: str = Field(min_length=1)


@router.get("/v1/tasks/{task_id}/logs", response_model=list[TaskLogDTO])
async def list_task_logs(
    task_id: UUID,
    _user: Annotated[CurrentUser, Depends(require_permission("viewTask"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[TaskLogDTO]:
    # Verify task ownership via org_id before exposing logs.
    t = (
        await db.execute(select(Task).where(Task.id == task_id, Task.organization_id == org_id))
    ).scalar_one_or_none()
    if not t:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "task_not_found")
    rows = (
        (
            await db.execute(
                select(TaskLog).where(TaskLog.task_id == task_id).order_by(TaskLog.created_at)
            )
        )
        .scalars()
        .all()
    )
    return [
        TaskLogDTO(
            id=log.id,
            task_id=log.task_id,
            author_id=log.author_id,
            content=log.content,
            created_at=log.created_at,
        )
        for log in rows
    ]


@router.post(
    "/v1/tasks/{task_id}/logs", response_model=TaskLogDTO, status_code=status.HTTP_201_CREATED
)
async def add_task_log(
    task_id: UUID,
    body: TaskLogCreate,
    user: Annotated[CurrentUser, Depends(require_permission("manageTask"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TaskLogDTO:
    t = (
        await db.execute(select(Task).where(Task.id == task_id, Task.organization_id == org_id))
    ).scalar_one_or_none()
    if not t:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "task_not_found")
    log = TaskLog(task_id=task_id, author_id=user.user_id, content=body.content)
    db.add(log)
    await db.flush()
    from adhkar.services.mentions import emit_mentions

    await emit_mentions(
        db,
        org_id=org_id,
        actor_user_id=user.user_id,
        content=body.content,
        extra_diff={
            "task_id": str(task_id),
            "case_id": str(t.case_id),
            "task_log_id": str(log.id),
        },
    )
    return TaskLogDTO(
        id=log.id,
        task_id=log.task_id,
        author_id=log.author_id,
        content=log.content,
        created_at=log.created_at,
    )
