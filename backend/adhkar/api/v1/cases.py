"""Case CRUD + Task CRUD endpoints (Phase 3)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import PlainTextResponse
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
    limit: int = 100,
) -> list[CaseDTO]:
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
    stmt = stmt.order_by(Case.number.desc()).limit(limit)
    rows = (await db.execute(stmt)).scalars().all()
    return [_case_to_dto(c) for c in rows]


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
) -> PlainTextResponse:
    """CSV dump matching GET /v1/tasks filter surface."""
    import csv  # noqa: PLC0415
    import io  # noqa: PLC0415

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
) -> PlainTextResponse:
    """CSV dump of cases in the current org. Same filter surface as the
    list endpoint (stage/severity/flagged) so a saved view can be exported."""
    import csv
    import io

    stmt = select(Case).where(Case.organization_id == org_id, Case.deleted_at.is_(None))
    if stage:
        stmt = stmt.where(Case.stage == stage)
    if severity is not None:
        stmt = stmt.where(Case.severity == severity)
    if flagged is not None:
        stmt = stmt.where(Case.flagged == flagged)
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
    limit: int = 200,
) -> list[TaskDTO]:
    """Cross-case task list. Used by the analyst's 'my queue' view.

    `mine=true` is shorthand for assignee_id=<current user>. `overdue=true`
    keeps only rows whose due_date is in the past AND whose status is not
    Completed/Cancelled."""
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
    stmt = stmt.order_by(Task.due_date.asc().nulls_last(), Task.created_at.desc()).limit(safe_limit)
    rows = (await db.execute(stmt)).scalars().all()
    return [_task_to_dto(t) for t in rows]


@router.get("/v1/cases/{case_id}/tasks", response_model=list[TaskDTO])
async def list_tasks(
    case_id: UUID,
    _user: Annotated[CurrentUser, Depends(require_permission("viewTask"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[TaskDTO]:
    await _load_case_or_404(db, org_id, case_id)
    rows = (
        (
            await db.execute(
                select(Task)
                .where(Task.case_id == case_id, Task.organization_id == org_id)
                .order_by(Task.order_index, Task.created_at)
            )
        )
        .scalars()
        .all()
    )
    return [_task_to_dto(t) for t in rows]


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
