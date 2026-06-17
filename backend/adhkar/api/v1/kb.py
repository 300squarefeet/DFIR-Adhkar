"""Knowledge base + case template endpoints (Phase 6)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal
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
from adhkar.db.models import Case, CaseTemplate, KnowledgeBasePage, Task
from adhkar.db.repositories.cases import CaseRepository

router = APIRouter(tags=["kb"])

TLP = Literal["white", "green", "amber", "amber-strict", "red"]
PAP = Literal["white", "green", "amber", "red"]


# ---------- Knowledge Base pages ----------


class KbPageDTO(BaseModel):
    id: UUID
    slug: str
    title: str
    content: str
    tags: list[str]
    pinned: bool
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime


class KbPageCreate(BaseModel):
    slug: str = Field(min_length=1, max_length=200, pattern=r"^[a-z0-9][a-z0-9-_]*$")
    title: str = Field(min_length=1, max_length=300)
    content: str = ""
    tags: list[str] = []
    pinned: bool = False


class KbPagePatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    content: str | None = None
    tags: list[str] | None = None
    pinned: bool | None = None


def _kb_dto(p: KnowledgeBasePage) -> KbPageDTO:
    return KbPageDTO(
        id=p.id,
        slug=p.slug,
        title=p.title,
        content=p.content,
        tags=list(p.tags),
        pinned=p.pinned,
        created_by=p.created_by,
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


@router.get("/v1/kb/pages", response_model=list[KbPageDTO])
async def list_kb_pages(
    _user: Annotated[CurrentUser, Depends(require_permission("viewCase"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
    query: str | None = None,
    limit: int = 100,
) -> list[KbPageDTO]:
    stmt = select(KnowledgeBasePage).where(KnowledgeBasePage.organization_id == org_id)
    if query:
        like = f"%{query}%"
        stmt = stmt.where(
            (KnowledgeBasePage.title.ilike(like)) | (KnowledgeBasePage.slug.ilike(like))
        )
    stmt = stmt.order_by(KnowledgeBasePage.pinned.desc(), KnowledgeBasePage.title).limit(limit)
    rows = (await db.execute(stmt)).scalars().all()
    return [_kb_dto(p) for p in rows]


@router.post("/v1/kb/pages", response_model=KbPageDTO, status_code=status.HTTP_201_CREATED)
async def create_kb_page(
    body: KbPageCreate,
    user: Annotated[CurrentUser, Depends(require_permission("manageConfig"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> KbPageDTO:
    p = KnowledgeBasePage(
        organization_id=org_id,
        slug=body.slug,
        title=body.title,
        content=body.content,
        tags=body.tags,
        pinned=body.pinned,
        created_by=user.user_id,
    )
    db.add(p)
    try:
        await db.flush()
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "slug_already_exists") from e
    return _kb_dto(p)


@router.get("/v1/kb/pages/{slug}", response_model=KbPageDTO)
async def get_kb_page(
    slug: str,
    _user: Annotated[CurrentUser, Depends(require_permission("viewCase"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> KbPageDTO:
    p = (
        await db.execute(
            select(KnowledgeBasePage).where(
                KnowledgeBasePage.organization_id == org_id, KnowledgeBasePage.slug == slug
            )
        )
    ).scalar_one_or_none()
    if not p:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "page_not_found")
    return _kb_dto(p)


@router.patch("/v1/kb/pages/{page_id}", response_model=KbPageDTO)
async def patch_kb_page(
    page_id: UUID,
    body: KbPagePatch,
    _user: Annotated[CurrentUser, Depends(require_permission("manageConfig"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> KbPageDTO:
    p = (
        await db.execute(
            select(KnowledgeBasePage).where(
                KnowledgeBasePage.id == page_id, KnowledgeBasePage.organization_id == org_id
            )
        )
    ).scalar_one_or_none()
    if not p:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "page_not_found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(p, field, value)
    await db.flush()
    return _kb_dto(p)


@router.delete("/v1/kb/pages/{page_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_kb_page(
    page_id: UUID,
    _user: Annotated[CurrentUser, Depends(require_permission("manageConfig"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    p = (
        await db.execute(
            select(KnowledgeBasePage).where(
                KnowledgeBasePage.id == page_id, KnowledgeBasePage.organization_id == org_id
            )
        )
    ).scalar_one_or_none()
    if not p:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "page_not_found")
    await db.delete(p)
    await db.flush()


# ---------- Case Templates ----------


class TemplateTaskSpec(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    group: str | None = None
    description: str | None = None
    order_index: int = 0
    mandatory: bool = False


class CaseTemplateDTO(BaseModel):
    id: UUID
    name: str
    display_name: str
    title_prefix: str | None
    severity: int
    tlp: str
    pap: str
    tags: list[str]
    description: str | None
    summary: str | None
    tasks: list[dict[str, Any]]
    custom_fields: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class CaseTemplateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200, pattern=r"^[a-z0-9][a-z0-9-_]*$")
    display_name: str = Field(min_length=1, max_length=300)
    title_prefix: str | None = Field(default=None, max_length=100)
    severity: int = Field(default=2, ge=1, le=4)
    tlp: TLP = "amber"
    pap: PAP = "amber"
    tags: list[str] = []
    description: str | None = None
    summary: str | None = None
    tasks: list[TemplateTaskSpec] = []
    custom_fields: dict[str, Any] = {}


class CaseTemplatePatch(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=300)
    title_prefix: str | None = Field(default=None, max_length=100)
    severity: int | None = Field(default=None, ge=1, le=4)
    tlp: TLP | None = None
    pap: PAP | None = None
    tags: list[str] | None = None
    description: str | None = None
    summary: str | None = None
    tasks: list[TemplateTaskSpec] | None = None
    custom_fields: dict[str, Any] | None = None


class ApplyTemplatePayload(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    description: str | None = None


def _template_dto(t: CaseTemplate) -> CaseTemplateDTO:
    return CaseTemplateDTO(
        id=t.id,
        name=t.name,
        display_name=t.display_name,
        title_prefix=t.title_prefix,
        severity=t.severity,
        tlp=t.tlp,
        pap=t.pap,
        tags=list(t.tags),
        description=t.description,
        summary=t.summary,
        tasks=list(t.tasks),
        custom_fields=dict(t.custom_fields),
        created_at=t.created_at,
        updated_at=t.updated_at,
    )


@router.get("/v1/case-templates", response_model=list[CaseTemplateDTO])
async def list_templates(
    _user: Annotated[CurrentUser, Depends(require_permission("viewCase"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[CaseTemplateDTO]:
    rows = (
        (
            await db.execute(
                select(CaseTemplate)
                .where(CaseTemplate.organization_id == org_id)
                .order_by(CaseTemplate.display_name)
            )
        )
        .scalars()
        .all()
    )
    return [_template_dto(t) for t in rows]


@router.post(
    "/v1/case-templates", response_model=CaseTemplateDTO, status_code=status.HTTP_201_CREATED
)
async def create_template(
    body: CaseTemplateCreate,
    user: Annotated[CurrentUser, Depends(require_permission("manageConfig"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CaseTemplateDTO:
    t = CaseTemplate(
        organization_id=org_id,
        name=body.name,
        display_name=body.display_name,
        title_prefix=body.title_prefix,
        severity=body.severity,
        tlp=body.tlp,
        pap=body.pap,
        tags=body.tags,
        description=body.description,
        summary=body.summary,
        tasks=[task.model_dump() for task in body.tasks],
        custom_fields=body.custom_fields,
        created_by=user.user_id,
    )
    db.add(t)
    try:
        await db.flush()
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "template_name_taken") from e
    return _template_dto(t)


@router.patch("/v1/case-templates/{template_id}", response_model=CaseTemplateDTO)
async def patch_template(
    template_id: UUID,
    body: CaseTemplatePatch,
    _user: Annotated[CurrentUser, Depends(require_permission("manageConfig"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CaseTemplateDTO:
    t = (
        await db.execute(
            select(CaseTemplate).where(
                CaseTemplate.id == template_id, CaseTemplate.organization_id == org_id
            )
        )
    ).scalar_one_or_none()
    if not t:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "template_not_found")
    patch = body.model_dump(exclude_unset=True)
    if "tasks" in patch and patch["tasks"] is not None:
        patch["tasks"] = [ts if isinstance(ts, dict) else ts.model_dump() for ts in patch["tasks"]]
    for field, value in patch.items():
        setattr(t, field, value)
    await db.flush()
    return _template_dto(t)


@router.delete("/v1/case-templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: UUID,
    _user: Annotated[CurrentUser, Depends(require_permission("manageConfig"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    t = (
        await db.execute(
            select(CaseTemplate).where(
                CaseTemplate.id == template_id, CaseTemplate.organization_id == org_id
            )
        )
    ).scalar_one_or_none()
    if not t:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "template_not_found")
    await db.delete(t)
    await db.flush()


@router.post("/v1/case-templates/{template_id}/apply", status_code=status.HTTP_201_CREATED)
async def apply_template(
    template_id: UUID,
    body: ApplyTemplatePayload,
    user: Annotated[CurrentUser, Depends(require_permission("manageCase"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    t = (
        await db.execute(
            select(CaseTemplate).where(
                CaseTemplate.id == template_id, CaseTemplate.organization_id == org_id
            )
        )
    ).scalar_one_or_none()
    if not t:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "template_not_found")
    repo = CaseRepository(db, org_id)
    number = await repo.next_number()
    title = f"{t.title_prefix} {body.title}" if t.title_prefix else body.title
    case = Case(
        organization_id=org_id,
        number=number,
        title=title,
        description=body.description or t.description,
        severity=t.severity,
        tlp=t.tlp,
        pap=t.pap,
        status="Open",
        stage="open",
        tags=list(t.tags),
        custom_fields=dict(t.custom_fields),
        created_by=user.user_id,
    )
    db.add(case)
    await db.flush()
    for task_spec in t.tasks:
        db.add(
            Task(
                organization_id=org_id,
                case_id=case.id,
                title=task_spec.get("title", "Untitled task"),
                group=task_spec.get("group"),
                description=task_spec.get("description"),
                status="Waiting",
                order_index=int(task_spec.get("order_index", 0)),
                mandatory=bool(task_spec.get("mandatory", False)),
            )
        )
    await db.flush()
    return {"case_id": str(case.id), "case_number": case.number}
