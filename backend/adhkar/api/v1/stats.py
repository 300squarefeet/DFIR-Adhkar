"""Aggregate time-series stats for dashboards (Phase 6).

Designed to feed the inline Sparkline component on the frontend without
needing a heavyweight metrics service. Org-scoped + viewCase-gated."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from adhkar.api.deps import (
    CurrentUser,
    get_db,
    require_current_org,
    require_permission,
)
from adhkar.db.models import Alert, Case, CaseTtp, TtpCatalogEntry

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


@router.get("/case-mttr", response_model=MttrResponse)
async def case_mttr(
    _user: Annotated[CurrentUser, Depends(require_permission("viewCase"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
    days: int = Query(default=30, ge=1, le=365),
) -> MttrResponse:
    """Mean-time-to-resolution per severity bucket for cases closed in the
    last `days` days. Hours = end_date - created_at. Median is computed
    in Python so we stay portable across PG versions; bucket sizes stay
    small (cap N per severity at the dialect default for percentile)."""
    since = datetime.now(tz=UTC) - timedelta(days=days)
    rows = (
        await db.execute(
            select(Case.severity, Case.created_at, Case.end_date).where(
                Case.organization_id == org_id,
                Case.deleted_at.is_(None),
                Case.stage == "closed",
                Case.end_date.is_not(None),
                Case.end_date >= since,
            )
        )
    ).all()
    by_sev: dict[int, list[float]] = {1: [], 2: [], 3: [], 4: []}
    for sev, created_at, end_date in rows:
        hrs = (end_date - created_at).total_seconds() / 3600.0
        if hrs >= 0 and sev in by_sev:
            by_sev[sev].append(hrs)
    buckets: list[MttrBucket] = []
    for sev in (1, 2, 3, 4):
        xs = sorted(by_sev[sev])
        n = len(xs)
        if n == 0:
            buckets.append(
                MttrBucket(severity=sev, closed_count=0, median_hours=None, mean_hours=None)
            )
            continue
        median = xs[n // 2] if n % 2 == 1 else (xs[n // 2 - 1] + xs[n // 2]) / 2
        mean = sum(xs) / n
        buckets.append(
            MttrBucket(
                severity=sev,
                closed_count=n,
                median_hours=round(median, 2),
                mean_hours=round(mean, 2),
            )
        )
    return MttrResponse(window_days=days, buckets=buckets)
