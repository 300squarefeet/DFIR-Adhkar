"""Aggregate time-series stats for dashboards (Phase 6).

Designed to feed the inline Sparkline component on the frontend without
needing a heavyweight metrics service. Org-scoped + viewCase-gated."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import case, distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from adhkar.api.deps import (
    CurrentUser,
    get_db,
    require_current_org,
    require_permission,
)
from adhkar.db.models import Alert, Case, CaseTtp, Observable, TtpCatalogEntry

router = APIRouter(prefix="/v1/stats", tags=["stats"])


class TimeSeriesPoint(BaseModel):
    day: str  # YYYY-MM-DD
    count: int


class TimeSeriesResponse(BaseModel):
    series: str
    points: list[TimeSeriesPoint]


def _last_n_days_keys(days: int) -> list[str]:
    today = datetime.now(tz=UTC).date()
    return [(today - timedelta(days=days - 1 - i)).isoformat() for i in range(days)]


async def _count_per_day(
    db: AsyncSession,
    org_id: UUID,
    entity: Literal["case", "alert"],
    days: int,
) -> list[TimeSeriesPoint]:
    table = Case if entity == "case" else Alert
    since = datetime.now(tz=UTC) - timedelta(days=days)
    day_col = func.date(table.created_at)
    stmt = (
        select(day_col.label("day"), func.count().label("n"))
        .where(table.organization_id == org_id, table.created_at >= since)
        .group_by(day_col)
    )
    rows = (await db.execute(stmt)).all()
    by_day: dict[str, int] = {}
    for row in rows:
        # day may be a date or string depending on dialect — normalize.
        day = row[0]
        key = day.isoformat() if hasattr(day, "isoformat") else str(day)
        by_day[key] = int(row[1])
    return [TimeSeriesPoint(day=k, count=by_day.get(k, 0)) for k in _last_n_days_keys(days)]


@router.get("/cases-per-day", response_model=TimeSeriesResponse)
async def cases_per_day(
    _user: Annotated[CurrentUser, Depends(require_permission("viewCase"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
    days: int = Query(default=14, ge=1, le=90),
) -> TimeSeriesResponse:
    """Cases created per day for the last N days, zero-filled."""
    return TimeSeriesResponse(
        series="cases-per-day",
        points=await _count_per_day(db, org_id, "case", days),
    )


class HeatmapEntry(BaseModel):
    technique_id: str
    name: str
    tactic: str
    case_count: int


class HeatmapResponse(BaseModel):
    entries: list[HeatmapEntry]


@router.get("/ttps-heatmap", response_model=HeatmapResponse)
async def ttps_heatmap(
    _user: Annotated[CurrentUser, Depends(require_permission("viewCase"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> HeatmapResponse:
    """Per-technique case count for the org, joined to the catalog so the
    UI can render an ATT&CK-navigator-style grouped grid (tactic →
    technique → case_count)."""
    rows = (
        await db.execute(
            select(
                CaseTtp.technique_id,
                func.count(distinct(CaseTtp.case_id)).label("n"),
            )
            .where(CaseTtp.organization_id == org_id)
            .group_by(CaseTtp.technique_id)
        )
    ).all()
    counts: dict[str, int] = {str(r[0]): int(r[1]) for r in rows}
    if not counts:
        return HeatmapResponse(entries=[])
    catalog = (
        (
            await db.execute(
                select(TtpCatalogEntry).where(TtpCatalogEntry.technique_id.in_(list(counts.keys())))
            )
        )
        .scalars()
        .all()
    )
    by_id = {c.technique_id: c for c in catalog}
    entries: list[HeatmapEntry] = []
    for tid, n in counts.items():
        cat = by_id.get(tid)
        entries.append(
            HeatmapEntry(
                technique_id=tid,
                name=cat.name if cat else "(unknown — not in catalog)",
                tactic=cat.tactic if cat else "uncategorized",
                case_count=n,
            )
        )
    entries.sort(key=lambda e: (e.tactic, -e.case_count, e.technique_id))
    return HeatmapResponse(entries=entries)


@router.get("/alerts-per-day", response_model=TimeSeriesResponse)
async def alerts_per_day(
    _user: Annotated[CurrentUser, Depends(require_permission("viewAlert"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
    days: int = Query(default=14, ge=1, le=90),
) -> TimeSeriesResponse:
    """Alerts ingested per day for the last N days, zero-filled."""
    return TimeSeriesResponse(
        series="alerts-per-day",
        points=await _count_per_day(db, org_id, "alert", days),
    )


class MttrBucket(BaseModel):
    severity: int
    closed_count: int
    median_hours: float | None
    mean_hours: float | None


class MttrResponse(BaseModel):
    window_days: int
    buckets: list[MttrBucket]
    prior_buckets: list[MttrBucket]


@router.get("/case-mttr", response_model=MttrResponse)
async def case_mttr(
    _user: Annotated[CurrentUser, Depends(require_permission("viewCase"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
    days: int = Query(default=30, ge=1, le=365),
) -> MttrResponse:
    """Mean-time-to-resolution per severity bucket for cases closed in the
    last `days` days, plus a `prior_buckets` slice covering the equally-sized
    previous window so the UI can render trend arrows. Hours = end_date -
    created_at. Median is computed in Python (portable across PG versions)."""
    now = datetime.now(tz=UTC)
    current_since = now - timedelta(days=days)
    prior_since = now - timedelta(days=days * 2)

    async def _slice(start: datetime, end: datetime) -> list[MttrBucket]:
        rows = (
            await db.execute(
                select(Case.severity, Case.created_at, Case.end_date).where(
                    Case.organization_id == org_id,
                    Case.deleted_at.is_(None),
                    Case.stage == "closed",
                    Case.end_date.is_not(None),
                    Case.end_date >= start,
                    Case.end_date < end,
                )
            )
        ).all()
        by_sev: dict[int, list[float]] = {1: [], 2: [], 3: [], 4: []}
        for sev, created_at, end_date in rows:
            hrs = (end_date - created_at).total_seconds() / 3600.0
            if hrs >= 0 and sev in by_sev:
                by_sev[sev].append(hrs)
        out: list[MttrBucket] = []
        for sev in (1, 2, 3, 4):
            xs = sorted(by_sev[sev])
            n = len(xs)
            if n == 0:
                out.append(
                    MttrBucket(severity=sev, closed_count=0, median_hours=None, mean_hours=None)
                )
                continue
            median = xs[n // 2] if n % 2 == 1 else (xs[n // 2 - 1] + xs[n // 2]) / 2
            mean = sum(xs) / n
            out.append(
                MttrBucket(
                    severity=sev,
                    closed_count=n,
                    median_hours=round(median, 2),
                    mean_hours=round(mean, 2),
                )
            )
        return out

    current = await _slice(current_since, now)
    prior = await _slice(prior_since, current_since)
    return MttrResponse(window_days=days, buckets=current, prior_buckets=prior)


class SlowestCase(BaseModel):
    id: UUID
    number: int
    title: str
    severity: int
    stage: str
    assignee_id: UUID | None
    hours_open: float


class SlowestCasesResponse(BaseModel):
    cases: list[SlowestCase]


@router.get("/slowest-open-cases", response_model=SlowestCasesResponse)
async def slowest_open_cases(
    _user: Annotated[CurrentUser, Depends(require_permission("viewCase"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(default=10, ge=1, le=50),
) -> SlowestCasesResponse:
    """Open cases sorted by age oldest-first so analysts can spot stale work."""
    now = datetime.now(tz=UTC)
    rows = (
        await db.execute(
            select(
                Case.id,
                Case.number,
                Case.title,
                Case.severity,
                Case.stage,
                Case.assignee_id,
                Case.created_at,
            )
            .where(
                Case.organization_id == org_id,
                Case.deleted_at.is_(None),
                Case.stage != "closed",
            )
            .order_by(Case.created_at.asc())
            .limit(limit)
        )
    ).all()
    cases: list[SlowestCase] = []
    for row in rows:
        hours_open = round((now - row.created_at).total_seconds() / 3600.0, 2)
        cases.append(
            SlowestCase(
                id=row.id,
                number=row.number,
                title=row.title,
                severity=row.severity,
                stage=row.stage,
                assignee_id=row.assignee_id,
                hours_open=hours_open,
            )
        )
    return SlowestCasesResponse(cases=cases)


class ObservableTypeBucket(BaseModel):
    data_type: str
    count: int


class ObservableTypesResponse(BaseModel):
    entries: list[ObservableTypeBucket]


@router.get("/observables-by-type", response_model=ObservableTypesResponse)
async def observables_by_type(
    _user: Annotated[CurrentUser, Depends(require_permission("viewObservable"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ObservableTypesResponse:
    """Count of non-deleted observables grouped by data_type for the org,
    ordered by count desc then data_type. Drives the IOC-composition
    breakdown panel."""
    rows = (
        await db.execute(
            select(Observable.data_type, func.count().label("n"))
            .where(Observable.organization_id == org_id, Observable.deleted_at.is_(None))
            .group_by(Observable.data_type)
            .order_by(func.count().desc(), Observable.data_type)
        )
    ).all()
    return ObservableTypesResponse(
        entries=[ObservableTypeBucket(data_type=str(r[0]), count=int(r[1])) for r in rows]
    )


class StageBucket(BaseModel):
    stage: str
    count: int


class CaseStagesResponse(BaseModel):
    entries: list[StageBucket]


@router.get("/case-stages", response_model=CaseStagesResponse)
async def case_stages(
    _user: Annotated[CurrentUser, Depends(require_permission("viewCase"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CaseStagesResponse:
    """Count of non-deleted cases grouped by stage (open/in_progress/closed)
    for the org. Zero-fills the three canonical stages so the UI doesn't
    need to special-case empty buckets."""
    rows = (
        await db.execute(
            select(Case.stage, func.count().label("n"))
            .where(Case.organization_id == org_id, Case.deleted_at.is_(None))
            .group_by(Case.stage)
        )
    ).all()
    by_stage: dict[str, int] = {str(r[0]): int(r[1]) for r in rows}
    return CaseStagesResponse(
        entries=[
            StageBucket(stage=s, count=by_stage.get(s, 0))
            for s in ("open", "in_progress", "closed")
        ]
    )


class AlertStatusBucket(BaseModel):
    status: str
    count: int


class AlertStatusesResponse(BaseModel):
    entries: list[AlertStatusBucket]


@router.get("/alerts-by-status", response_model=AlertStatusesResponse)
async def alerts_by_status(
    _user: Annotated[CurrentUser, Depends(require_permission("viewAlert"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AlertStatusesResponse:
    """Count alerts grouped by status, zero-filled over the four canonical
    statuses (New/Updated/Ignored/Imported)."""
    rows = (
        await db.execute(
            select(Alert.status, func.count().label("n"))
            .where(Alert.organization_id == org_id)
            .group_by(Alert.status)
        )
    ).all()
    by_status: dict[str, int] = {str(r[0]): int(r[1]) for r in rows}
    canonical = ("New", "Updated", "Ignored", "Imported")
    return AlertStatusesResponse(
        entries=[AlertStatusBucket(status=s, count=by_status.get(s, 0)) for s in canonical]
    )


@router.get("/audit-per-day", response_model=TimeSeriesResponse)
async def audit_per_day(
    _user: Annotated[CurrentUser, Depends(require_permission("viewAudit"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
    days: int = Query(default=14, ge=1, le=90),
) -> TimeSeriesResponse:
    """Audit-log row count per day for the last N days, zero-filled.
    Useful for spotting activity spikes."""
    from adhkar.db.models import AuditLog as _AuditLog

    since = datetime.now(tz=UTC) - timedelta(days=days)
    day_col = func.date(_AuditLog.created_at)
    stmt = (
        select(day_col.label("day"), func.count().label("n"))
        .where(_AuditLog.organization_id == org_id, _AuditLog.created_at >= since)
        .group_by(day_col)
    )
    rows = (await db.execute(stmt)).all()
    by_day: dict[str, int] = {}
    for row in rows:
        day = row[0]
        key = day.isoformat() if hasattr(day, "isoformat") else str(day)
        by_day[key] = int(row[1])
    return TimeSeriesResponse(
        series="audit-per-day",
        points=[TimeSeriesPoint(day=k, count=by_day.get(k, 0)) for k in _last_n_days_keys(days)],
    )


class TlpBucket(BaseModel):
    tlp: str
    count: int


class TlpResponse(BaseModel):
    entries: list[TlpBucket]


@router.get("/observables-by-tlp", response_model=TlpResponse)
async def observables_by_tlp(
    _user: Annotated[CurrentUser, Depends(require_permission("viewObservable"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TlpResponse:
    """Counts grouped by TLP (white/green/amber/amber-strict/red), zero-filled."""
    rows = (
        await db.execute(
            select(Observable.tlp, func.count().label("n"))
            .where(Observable.organization_id == org_id, Observable.deleted_at.is_(None))
            .group_by(Observable.tlp)
        )
    ).all()
    by_tlp: dict[str, int] = {str(r[0]): int(r[1]) for r in rows}
    canonical = ("white", "green", "amber", "amber-strict", "red")
    return TlpResponse(entries=[TlpBucket(tlp=t, count=by_tlp.get(t, 0)) for t in canonical])


class CaseTlpBucket(BaseModel):
    tlp: str
    open_count: int
    closed_count: int


class CasesByTlpResponse(BaseModel):
    entries: list[CaseTlpBucket]


@router.get("/cases-by-tlp", response_model=CasesByTlpResponse)
async def cases_by_tlp(
    _user: Annotated[CurrentUser, Depends(require_permission("viewCase"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CasesByTlpResponse:
    """Per-TLP open/closed case counts. Returns all five canonical TLP
    buckets even when empty so the UI can keep the legend stable."""
    rows = (
        await db.execute(
            select(
                Case.tlp,
                func.sum(case((Case.stage != "closed", 1), else_=0)).label("open_n"),
                func.sum(case((Case.stage == "closed", 1), else_=0)).label("closed_n"),
            )
            .where(Case.organization_id == org_id, Case.deleted_at.is_(None))
            .group_by(Case.tlp)
        )
    ).all()
    by_tlp: dict[str, tuple[int, int]] = {str(r[0]): (int(r[1] or 0), int(r[2] or 0)) for r in rows}
    canonical = ("white", "green", "amber", "amber-strict", "red")
    entries: list[CaseTlpBucket] = []
    for t in canonical:
        opn, cls = by_tlp.get(t, (0, 0))
        entries.append(CaseTlpBucket(tlp=t, open_count=opn, closed_count=cls))
    return CasesByTlpResponse(entries=entries)


class AssigneeBucket(BaseModel):
    assignee_id: UUID | None
    open_count: int
    closed_count: int


class CasesByAssigneeResponse(BaseModel):
    entries: list[AssigneeBucket]


@router.get("/cases-by-assignee", response_model=CasesByAssigneeResponse)
async def cases_by_assignee(
    _user: Annotated[CurrentUser, Depends(require_permission("viewCase"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CasesByAssigneeResponse:
    """Per-assignee workload: open and closed case counts. `assignee_id`
    is null in the 'unassigned' bucket. Ordered by open_count DESC then
    closed_count DESC."""
    rows = (
        await db.execute(
            select(
                Case.assignee_id,
                func.sum(case((Case.stage != "closed", 1), else_=0)).label("open_n"),
                func.sum(case((Case.stage == "closed", 1), else_=0)).label("closed_n"),
            )
            .where(Case.organization_id == org_id, Case.deleted_at.is_(None))
            .group_by(Case.assignee_id)
        )
    ).all()
    buckets: list[AssigneeBucket] = []
    for row in rows:
        buckets.append(
            AssigneeBucket(
                assignee_id=row[0],
                open_count=int(row[1] or 0),
                closed_count=int(row[2] or 0),
            )
        )
    buckets.sort(key=lambda b: (-b.open_count, -b.closed_count))
    return CasesByAssigneeResponse(entries=buckets)


class AlertSourceBucket(BaseModel):
    source: str
    count: int


class AlertSourcesResponse(BaseModel):
    entries: list[AlertSourceBucket]


@router.get("/alerts-by-source", response_model=AlertSourcesResponse)
async def alerts_by_source(
    _user: Annotated[CurrentUser, Depends(require_permission("viewAlert"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(default=10, ge=1, le=50),
) -> AlertSourcesResponse:
    """Counts of alerts grouped by `source` (e.g. splunk, sentinel,
    custom). Ordered count DESC, top-N. Helps spot ingest pipelines
    that are noisier than expected."""
    rows = (
        await db.execute(
            select(Alert.source, func.count().label("n"))
            .where(Alert.organization_id == org_id)
            .group_by(Alert.source)
            .order_by(func.count().desc(), Alert.source)
            .limit(limit)
        )
    ).all()
    return AlertSourcesResponse(
        entries=[AlertSourceBucket(source=str(r[0]), count=int(r[1])) for r in rows]
    )


class TaskStatusBucket(BaseModel):
    status: str
    count: int


class TasksByStatusResponse(BaseModel):
    entries: list[TaskStatusBucket]


@router.get("/tasks-by-status", response_model=TasksByStatusResponse)
async def tasks_by_status(
    _user: Annotated[CurrentUser, Depends(require_permission("viewTask"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TasksByStatusResponse:
    """Counts tasks grouped by status, zero-filled across the four
    canonical statuses (Waiting/InProgress/Completed/Cancelled)."""
    from adhkar.db.models import Task as _Task

    rows = (
        await db.execute(
            select(_Task.status, func.count().label("n"))
            .where(_Task.organization_id == org_id)
            .group_by(_Task.status)
        )
    ).all()
    by_status: dict[str, int] = {str(r[0]): int(r[1]) for r in rows}
    canonical = ("Waiting", "InProgress", "Completed", "Cancelled")
    return TasksByStatusResponse(
        entries=[TaskStatusBucket(status=s, count=by_status.get(s, 0)) for s in canonical]
    )


class PapBucket(BaseModel):
    pap: str
    count: int


class PapResponse(BaseModel):
    entries: list[PapBucket]


@router.get("/observables-by-pap", response_model=PapResponse)
async def observables_by_pap(
    _user: Annotated[CurrentUser, Depends(require_permission("viewObservable"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PapResponse:
    """Counts grouped by PAP (white/green/amber/red), zero-filled."""
    rows = (
        await db.execute(
            select(Observable.pap, func.count().label("n"))
            .where(Observable.organization_id == org_id, Observable.deleted_at.is_(None))
            .group_by(Observable.pap)
        )
    ).all()
    by_pap: dict[str, int] = {str(r[0]): int(r[1]) for r in rows}
    canonical = ("white", "green", "amber", "red")
    return PapResponse(entries=[PapBucket(pap=p, count=by_pap.get(p, 0)) for p in canonical])
