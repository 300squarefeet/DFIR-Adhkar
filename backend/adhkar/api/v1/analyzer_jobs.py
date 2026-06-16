"""Analyzer job endpoints (Phase 2)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from adhkar.analyzers._bootstrap import register_builtins
from adhkar.analyzers.registry import get_registry
from adhkar.api.deps import CurrentUser, get_db, require_current_org, require_permission
from adhkar.db.models import AnalyzerJob, Observable

router = APIRouter(tags=["analyzers"])

register_builtins()


class AnalyzerInfoDTO(BaseModel):
    name: str
    description: str
    supported_types: list[str]


class JobDTO(BaseModel):
    id: UUID
    organization_id: UUID
    observable_id: UUID
    analyzer_name: str
    status: str
    report: dict[str, Any] | None
    error_message: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime


def _to_dto(j: AnalyzerJob) -> JobDTO:
    return JobDTO(
        id=j.id,
        organization_id=j.organization_id,
        observable_id=j.observable_id,
        analyzer_name=j.analyzer_name,
        status=j.status,
        report=j.report,
        error_message=j.error_message,
        started_at=j.started_at,
        finished_at=j.finished_at,
        created_at=j.created_at,
    )


@router.get("/v1/analyzers", response_model=list[AnalyzerInfoDTO])
async def list_analyzers(
    _user: Annotated[CurrentUser, Depends(require_permission("viewObservable"))],
) -> list[AnalyzerInfoDTO]:
    return [
        AnalyzerInfoDTO(
            name=a.name,
            description=a.description,
            supported_types=sorted(a.supported_types),
        )
        for a in get_registry().all()
    ]


@router.post(
    "/v1/observables/{observable_id}/analyzers/{analyzer_name}",
    response_model=JobDTO,
    status_code=status.HTTP_201_CREATED,
)
async def enqueue_job(
    observable_id: UUID,
    analyzer_name: str,
    user: Annotated[CurrentUser, Depends(require_permission("manageObservable"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JobDTO:
    obs = (
        await db.execute(
            select(Observable).where(
                Observable.id == observable_id,
                Observable.organization_id == org_id,
                Observable.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if not obs:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "observable_not_found")
    analyzer = get_registry().get(analyzer_name)
    if not analyzer:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "analyzer_not_found")
    if obs.data_type not in analyzer.supported_types:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "analyzer_does_not_support_data_type"
        )
    job = AnalyzerJob(
        organization_id=org_id,
        observable_id=observable_id,
        analyzer_name=analyzer_name,
        status="queued",
        created_by=user.user_id,
    )
    db.add(job)
    await db.flush()
    return _to_dto(job)


@router.get(
    "/v1/observables/{observable_id}/analyzer-jobs", response_model=list[JobDTO]
)
async def list_jobs_for_observable(
    observable_id: UUID,
    _user: Annotated[CurrentUser, Depends(require_permission("viewObservable"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[JobDTO]:
    rows = (
        await db.execute(
            select(AnalyzerJob).where(
                AnalyzerJob.observable_id == observable_id,
                AnalyzerJob.organization_id == org_id,
            )
        )
    ).scalars().all()
    return [_to_dto(j) for j in rows]


@router.get("/v1/analyzer-jobs/{job_id}", response_model=JobDTO)
async def get_job(
    job_id: UUID,
    _user: Annotated[CurrentUser, Depends(require_permission("viewObservable"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JobDTO:
    row = (
        await db.execute(
            select(AnalyzerJob).where(
                AnalyzerJob.id == job_id, AnalyzerJob.organization_id == org_id
            )
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "job_not_found")
    return _to_dto(row)
