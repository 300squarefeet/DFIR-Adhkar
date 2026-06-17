"""Observable CSV importer + MISP-style JSON exporter.

CSV format (header REQUIRED):
    data_type,data,tlp,is_ioc,tags,message
    ip,1.2.3.4,amber,true,"phish,acme",seen in mail bounce
    domain,acme-phish.example,red,true,phish,

- Quoted commas inside tags are handled (Python csv module).
- Unknown columns ignored. Missing rows are dropped (no exception).
- One-shot dedup: rows whose (data_type, data, case_id) already exist
  are skipped to keep imports idempotent."""

from __future__ import annotations

import csv
import io
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from adhkar.api.deps import (
    CurrentUser,
    get_db,
    require_current_org,
    require_permission,
)
from adhkar.audit import audit_and_emit
from adhkar.db.models import Case, Observable

router = APIRouter(tags=["observables"])

_VALID_TLP = frozenset({"white", "green", "amber", "amber-strict", "red"})


class CsvImportPayload(BaseModel):
    csv_text: str = Field(min_length=1, max_length=10_485_760)  # 10 MiB cap
    case_id: UUID | None = None


class CsvImportResult(BaseModel):
    imported: int
    skipped_duplicate: int
    skipped_invalid: int


def _parse_bool(value: str) -> bool:
    return value.strip().lower() in ("1", "true", "yes", "y", "t")


def _split_tags(raw: str) -> list[str]:
    return [t.strip() for t in raw.split(",") if t.strip()]


@router.post("/v1/observables/import-csv", response_model=CsvImportResult)
async def import_observables_csv(
    body: CsvImportPayload,
    user: Annotated[CurrentUser, Depends(require_permission("manageObservable"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CsvImportResult:
    case_id = body.case_id
    if case_id is not None:
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
    reader = csv.DictReader(io.StringIO(body.csv_text))
    if (
        reader.fieldnames is None
        or "data_type" not in reader.fieldnames
        or "data" not in reader.fieldnames
    ):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "csv_missing_required_columns_data_type_and_data"
        )
    imported = 0
    duplicate = 0
    invalid = 0
    new_ids: list[UUID] = []
    for row in reader:
        data_type = (row.get("data_type") or "").strip()
        data = (row.get("data") or "").strip()
        if not data_type or not data:
            invalid += 1
            continue
        tlp = (row.get("tlp") or "amber").strip().lower()
        if tlp not in _VALID_TLP:
            tlp = "amber"
        # Dedup vs existing rows in this org (+ same case if scoped)
        dup_stmt = select(Observable.id).where(
            Observable.organization_id == org_id,
            Observable.data_type == data_type,
            Observable.data == data,
            Observable.deleted_at.is_(None),
        )
        if case_id is not None:
            dup_stmt = dup_stmt.where(Observable.case_id == case_id)
        existing = (await db.execute(dup_stmt)).first()
        if existing is not None:
            duplicate += 1
            continue
        o = Observable(
            organization_id=org_id,
            case_id=case_id,
            data_type=data_type[:50],
            data=data[:2000],
            tlp=tlp,
            pap="amber",
            tags=_split_tags(row.get("tags", "")),
            is_ioc=_parse_bool(row.get("is_ioc", "")),
            sighted=_parse_bool(row.get("sighted", "")),
            message=(row.get("message") or "").strip() or None,
            created_by=user.user_id,
        )
        db.add(o)
        await db.flush()
        new_ids.append(o.id)
        imported += 1
    if imported > 0:
        await audit_and_emit(
            db,
            actor_user_id=user.user_id,
            organization_id=org_id,
            action="csv_imported",
            entity_type="observable",
            entity_id=None,
            diff={
                "count": imported,
                "case_id": str(case_id) if case_id else None,
                "ids": [str(i) for i in new_ids[:50]],
            },
        )
    return CsvImportResult(
        imported=imported,
        skipped_duplicate=duplicate,
        skipped_invalid=invalid,
    )


class MispExportEntry(BaseModel):
    type: str
    value: str
    to_ids: bool
    comment: str | None
    tags: list[str]


class MispExportResponse(BaseModel):
    case_number: int | None
    case_title: str | None
    attributes: list[MispExportEntry]


# Map our IOC types onto MISP attribute names. Unmapped types fall through
# unchanged so MISP imports them as-is.
_MISP_TYPE_MAP = {
    "ip": "ip-dst",
    "domain": "domain",
    "url": "url",
    "hash": "md5",
    "email": "email-src",
    "filename": "filename",
}


@router.get(
    "/v1/cases/{case_id}/observables/export-misp",
    response_model=MispExportResponse,
)
async def export_observables_to_misp(
    case_id: UUID,
    _user: Annotated[CurrentUser, Depends(require_permission("viewCase"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MispExportResponse:
    """Build a MISP-compatible attributes list from a case's observables.

    The shape mirrors what a MISP /events/restSearch caller would expect
    so the user can copy-paste into a MISP event without reshaping."""
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
    rows = (
        (
            await db.execute(
                select(Observable).where(
                    Observable.organization_id == org_id,
                    Observable.case_id == case_id,
                    Observable.deleted_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    attrs: list[MispExportEntry] = []
    for o in rows:
        attrs.append(
            MispExportEntry(
                type=_MISP_TYPE_MAP.get(o.data_type, o.data_type),
                value=o.data,
                to_ids=o.is_ioc,
                comment=o.message,
                tags=list(o.tags),
            )
        )
    return MispExportResponse(case_number=case.number, case_title=case.title, attributes=attrs)


@router.get(
    "/v1/observables/export-csv",
    response_class=PlainTextResponse,
    responses={200: {"content": {"text/csv": {}}}},
)
async def export_observables_csv(
    _user: Annotated[CurrentUser, Depends(require_permission("viewObservable"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
    case_id: UUID | None = None,
    is_ioc: bool | None = None,
    data_type: str | None = None,
    sighted: bool | None = None,
    tlp: str | None = None,
    tag: str | None = None,
) -> PlainTextResponse:
    """Round-trip-compatible inverse of /v1/observables/import-csv.

    Same header order so an exported file can be re-imported without
    reshaping. Optional filters mirror the list endpoint."""
    stmt = select(Observable).where(
        Observable.organization_id == org_id, Observable.deleted_at.is_(None)
    )
    if case_id is not None:
        stmt = stmt.where(Observable.case_id == case_id)
    if is_ioc is not None:
        stmt = stmt.where(Observable.is_ioc.is_(is_ioc))
    if data_type:
        stmt = stmt.where(Observable.data_type == data_type)
    if sighted is not None:
        stmt = stmt.where(Observable.sighted.is_(sighted))
    if tlp:
        stmt = stmt.where(Observable.tlp == tlp)
    if tag:
        stmt = stmt.where(Observable.tags.contains([tag]))
    rows = (await db.execute(stmt.order_by(Observable.created_at))).scalars().all()
    buf = io.StringIO()
    writer = csv.writer(buf, quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
    writer.writerow(["data_type", "data", "tlp", "is_ioc", "tags", "message"])
    for o in rows:
        writer.writerow(
            [
                o.data_type,
                o.data,
                o.tlp,
                "true" if o.is_ioc else "false",
                ",".join(o.tags),
                o.message or "",
            ]
        )
    return PlainTextResponse(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="adhkar-observables.csv"'},
    )
