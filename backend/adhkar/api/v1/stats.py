"""Aggregate time-series stats for dashboards (Phase 6).

Designed to feed the inline Sparkline component on the frontend without
needing a heavyweight metrics service. Org-scoped + viewCase-gated."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from adhkar.api.deps import (
    CurrentUser,
    get_db,
    require_current_org,
    require_permission,
)
from adhkar.db.models import Alert, Case

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
