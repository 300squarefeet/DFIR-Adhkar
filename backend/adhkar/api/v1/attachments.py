"""Attachment + Case share endpoints (Phase 9).

The actual blob upload integration with MinIO/S3 lives in adhkar.storage
(deferred to Phase 9b). This endpoint records the attachment metadata once
the caller has uploaded the blob to the configured object store and gives
us the storage_key. For Phase 9a we accept a JSON envelope with the
storage_key + sha256 and trust the caller; later we'll switch to a
presigned-PUT flow + AV scan webhook."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
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
from adhkar.core.settings import get_settings
from adhkar.db.models import Attachment, Case, CaseShare, Task, User
from adhkar.storage.presigned import S3Config, presigned_put_url

router = APIRouter(tags=["attachments"])


class PresignRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=500)
    content_type: str = Field(min_length=1, max_length=200)


class PresignResponse(BaseModel):
    url: str
    storage_key: str
    expires_in: int


def _s3_from_settings() -> S3Config:
    s = get_settings()
    return S3Config(
        region=s.s3_region,
        bucket=s.s3_bucket,
        endpoint=s.s3_endpoint,
        access_key_id=s.s3_access_key,
        secret_access_key=s.s3_secret_key,
        path_style=True,
    )


@router.post("/v1/attachments/presign", response_model=PresignResponse)
async def presign_upload(
    body: PresignRequest,
    _user: Annotated[CurrentUser, Depends(require_permission("manageCase"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
) -> PresignResponse:
    """Hand the client a presigned PUT URL for direct upload to MinIO/S3.

    The client uploads the blob, then POSTs to /v1/cases/{id}/attachments
    with the returned storage_key + sha256."""
    cfg = _s3_from_settings()
    from uuid import uuid4 as _uuid4

    key = f"org/{org_id}/{_uuid4()}/{body.filename}"
    expires = 3600
    url = presigned_put_url(cfg, key, body.content_type, expires)
    return PresignResponse(url=url, storage_key=key, expires_in=expires)


# ---------- Attachments ----------


class AttachmentDTO(BaseModel):
    id: UUID
    case_id: UUID | None
    task_id: UUID | None
    filename: str
    content_type: str
    size_bytes: int
    sha256: str
    storage_key: str
    is_quarantined: bool
    av_scan_status: str
    uploaded_by: UUID | None
    created_at: datetime


class AttachmentRegister(BaseModel):
    filename: str = Field(min_length=1, max_length=500)
    content_type: str = Field(min_length=1, max_length=200)
    size_bytes: int = Field(ge=0, le=10_737_418_240)  # 10 GiB hard cap
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    storage_key: str = Field(min_length=1, max_length=500)
    is_quarantined: bool = False


class AttachmentScanUpdate(BaseModel):
    av_scan_status: Literal["clean", "infected", "skipped"]


def _att_dto(a: Attachment) -> AttachmentDTO:
    return AttachmentDTO(
        id=a.id,
        case_id=a.case_id,
        task_id=a.task_id,
        filename=a.filename,
        content_type=a.content_type,
        size_bytes=a.size_bytes,
        sha256=a.sha256,
        storage_key=a.storage_key,
        is_quarantined=a.is_quarantined,
        av_scan_status=a.av_scan_status,
        uploaded_by=a.uploaded_by,
        created_at=a.created_at,
    )


@router.post(
    "/v1/cases/{case_id}/attachments",
    response_model=AttachmentDTO,
    status_code=status.HTTP_201_CREATED,
)
async def register_case_attachment(
    case_id: UUID,
    body: AttachmentRegister,
    user: Annotated[CurrentUser, Depends(require_permission("manageCase"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AttachmentDTO:
    c = (
        await db.execute(
            select(Case).where(
                Case.id == case_id, Case.organization_id == org_id, Case.deleted_at.is_(None)
            )
        )
    ).scalar_one_or_none()
    if not c:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "case_not_found")
    a = Attachment(
        organization_id=org_id,
        case_id=case_id,
        task_id=None,
        filename=body.filename,
        content_type=body.content_type,
        size_bytes=body.size_bytes,
        sha256=body.sha256,
        storage_key=body.storage_key,
        is_quarantined=body.is_quarantined,
        uploaded_by=user.user_id,
    )
    db.add(a)
    await db.flush()
    return _att_dto(a)


@router.post(
    "/v1/tasks/{task_id}/attachments",
    response_model=AttachmentDTO,
    status_code=status.HTTP_201_CREATED,
)
async def register_task_attachment(
    task_id: UUID,
    body: AttachmentRegister,
    user: Annotated[CurrentUser, Depends(require_permission("manageTask"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AttachmentDTO:
    t = (
        await db.execute(select(Task).where(Task.id == task_id, Task.organization_id == org_id))
    ).scalar_one_or_none()
    if not t:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "task_not_found")
    a = Attachment(
        organization_id=org_id,
        case_id=t.case_id,
        task_id=task_id,
        filename=body.filename,
        content_type=body.content_type,
        size_bytes=body.size_bytes,
        sha256=body.sha256,
        storage_key=body.storage_key,
        is_quarantined=body.is_quarantined,
        uploaded_by=user.user_id,
    )
    db.add(a)
    await db.flush()
    return _att_dto(a)


@router.get("/v1/cases/{case_id}/attachments", response_model=list[AttachmentDTO])
async def list_case_attachments(
    case_id: UUID,
    _user: Annotated[CurrentUser, Depends(require_permission("viewCase"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[AttachmentDTO]:
    rows = (
        (
            await db.execute(
                select(Attachment)
                .where(Attachment.organization_id == org_id, Attachment.case_id == case_id)
                .order_by(Attachment.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return [_att_dto(a) for a in rows]


@router.patch("/v1/attachments/{attachment_id}/av-scan", response_model=AttachmentDTO)
async def set_av_scan(
    attachment_id: UUID,
    body: AttachmentScanUpdate,
    _user: Annotated[CurrentUser, Depends(require_permission("manageCase"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AttachmentDTO:
    a = (
        await db.execute(
            select(Attachment).where(
                Attachment.id == attachment_id, Attachment.organization_id == org_id
            )
        )
    ).scalar_one_or_none()
    if not a:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "attachment_not_found")
    a.av_scan_status = body.av_scan_status
    if body.av_scan_status == "clean":
        a.is_quarantined = False
    await db.flush()
    return _att_dto(a)


@router.delete("/v1/attachments/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_attachment(
    attachment_id: UUID,
    _user: Annotated[CurrentUser, Depends(require_permission("manageCase"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    a = (
        await db.execute(
            select(Attachment).where(
                Attachment.id == attachment_id, Attachment.organization_id == org_id
            )
        )
    ).scalar_one_or_none()
    if not a:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "attachment_not_found")
    await db.delete(a)
    await db.flush()


# ---------- Case shares (Portal access) ----------


class CaseShareDTO(BaseModel):
    id: UUID
    case_id: UUID
    user_id: UUID
    can_comment: bool
    can_upload: bool
    granted_by: UUID | None
    created_at: datetime
    revoked_at: datetime | None


class CaseShareCreate(BaseModel):
    user_id: UUID
    can_comment: bool = False
    can_upload: bool = False


def _share_dto(s: CaseShare) -> CaseShareDTO:
    return CaseShareDTO(
        id=s.id,
        case_id=s.case_id,
        user_id=s.user_id,
        can_comment=s.can_comment,
        can_upload=s.can_upload,
        granted_by=s.granted_by,
        created_at=s.created_at,
        revoked_at=s.revoked_at,
    )


@router.get("/v1/cases/{case_id}/shares", response_model=list[CaseShareDTO])
async def list_shares(
    case_id: UUID,
    _user: Annotated[CurrentUser, Depends(require_permission("manageCase"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[CaseShareDTO]:
    rows = (
        (
            await db.execute(
                select(CaseShare).where(
                    CaseShare.case_id == case_id, CaseShare.organization_id == org_id
                )
            )
        )
        .scalars()
        .all()
    )
    return [_share_dto(s) for s in rows]


@router.post(
    "/v1/cases/{case_id}/shares",
    response_model=CaseShareDTO,
    status_code=status.HTTP_201_CREATED,
)
async def grant_share(
    case_id: UUID,
    body: CaseShareCreate,
    user: Annotated[CurrentUser, Depends(require_permission("manageCase"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CaseShareDTO:
    c = (
        await db.execute(
            select(Case).where(
                Case.id == case_id, Case.organization_id == org_id, Case.deleted_at.is_(None)
            )
        )
    ).scalar_one_or_none()
    if not c:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "case_not_found")
    grantee = (await db.execute(select(User).where(User.id == body.user_id))).scalar_one_or_none()
    if not grantee:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user_not_found")
    s = CaseShare(
        organization_id=org_id,
        case_id=case_id,
        user_id=body.user_id,
        can_comment=body.can_comment,
        can_upload=body.can_upload,
        granted_by=user.user_id,
    )
    db.add(s)
    try:
        await db.flush()
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "share_already_exists") from e
    return _share_dto(s)


@router.delete("/v1/case-shares/{share_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_share(
    share_id: UUID,
    _user: Annotated[CurrentUser, Depends(require_permission("manageCase"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    s = (
        await db.execute(
            select(CaseShare).where(CaseShare.id == share_id, CaseShare.organization_id == org_id)
        )
    ).scalar_one_or_none()
    if not s:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "share_not_found")
    from datetime import UTC

    s.revoked_at = datetime.now(tz=UTC)
    await db.flush()
