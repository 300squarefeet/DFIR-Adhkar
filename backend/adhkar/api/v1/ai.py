"""Adhkar Mind endpoints (Phase 8).

Currently provides:
- POST /v1/ai/cases/{case_id}/summarize — produce an analyst-facing summary
- POST /v1/ai/cases/{case_id}/suggest-next-steps — recommend next investigation steps
- POST /v1/ai/freeform — ad-hoc prompt with case context injection
- GET  /v1/ai/calls — list recent AI calls (audit visibility)

All routes use the LLM router; default provider is the in-process stub so
the system runs offline. Provider selection per call is via JWT-org-scoped
config (deferred); for now, defaults are honored."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from adhkar.ai.agent import run_agent
from adhkar.ai.router import LlmRequest, get_router
from adhkar.api.deps import (
    CurrentUser,
    get_db,
    require_current_org,
    require_permission,
)
from adhkar.db.models import AiCall, Case, Task

router = APIRouter(prefix="/v1/ai", tags=["ai"])


class AiCallDTO(BaseModel):
    id: UUID
    case_id: UUID | None
    purpose: str
    provider: str
    model: str
    prompt: str
    response_text: str
    input_tokens: int
    output_tokens: int
    created_at: datetime


class FreeformPayload(BaseModel):
    prompt: str = Field(min_length=1, max_length=8000)
    case_id: UUID | None = None
    provider: str | None = None
    model: str | None = None


class AiResponseDTO(BaseModel):
    response: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int


def _to_dto(c: AiCall) -> AiCallDTO:
    return AiCallDTO(
        id=c.id,
        case_id=c.case_id,
        purpose=c.purpose,
        provider=c.provider,
        model=c.model,
        prompt=c.prompt,
        response_text=c.response_text,
        input_tokens=c.input_tokens,
        output_tokens=c.output_tokens,
        created_at=c.created_at,
    )


async def _load_case(db: AsyncSession, org_id: UUID, case_id: UUID) -> Case:
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


async def _case_context(db: AsyncSession, org_id: UUID, case: Case) -> str:
    tasks = (
        (
            await db.execute(
                select(Task)
                .where(Task.organization_id == org_id, Task.case_id == case.id)
                .order_by(Task.order_index)
            )
        )
        .scalars()
        .all()
    )
    parts = [
        f"Case #{case.number}: {case.title}",
        f"Severity: {case.severity}  TLP: {case.tlp}  Status: {case.status}",
        f"Description: {case.description or '(none)'}",
        f"Tags: {', '.join(case.tags) or '(none)'}",
        f"Tasks ({len(tasks)}):",
    ]
    for t in tasks[:20]:
        parts.append(f"  - [{t.status}] {t.title}")
    return "\n".join(parts)


async def _generate_and_log(
    db: AsyncSession,
    org_id: UUID,
    user_id: UUID | None,
    case_id: UUID | None,
    purpose: str,
    system: str,
    user_prompt: str,
    provider: str | None,
    model: str | None,
    extra: dict[str, Any] | None = None,
) -> AiResponseDTO:
    router_ = get_router()
    req = LlmRequest(
        system=system,
        messages=[{"role": "user", "content": user_prompt}],
        model=model,
    )
    resp = await router_.generate(req, provider=provider)
    db.add(
        AiCall(
            organization_id=org_id,
            user_id=user_id,
            case_id=case_id,
            purpose=purpose,
            provider=resp.provider,
            model=resp.model,
            prompt=user_prompt,
            response_text=resp.text,
            input_tokens=resp.input_tokens,
            output_tokens=resp.output_tokens,
            extra=extra or {},
        )
    )
    await db.flush()
    return AiResponseDTO(
        response=resp.text,
        provider=resp.provider,
        model=resp.model,
        input_tokens=resp.input_tokens,
        output_tokens=resp.output_tokens,
    )


@router.post("/cases/{case_id}/summarize", response_model=AiResponseDTO)
async def summarize_case(
    case_id: UUID,
    user: Annotated[CurrentUser, Depends(require_permission("viewCase"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AiResponseDTO:
    case = await _load_case(db, org_id, case_id)
    ctx = await _case_context(db, org_id, case)
    return await _generate_and_log(
        db,
        org_id,
        user.user_id,
        case_id,
        purpose="summarize_case",
        system="You are a SOC analyst assistant. Summarize the case concisely.",
        user_prompt=f"Summarize this case for handoff:\n\n{ctx}",
        provider=None,
        model=None,
    )


@router.post("/cases/{case_id}/suggest-next-steps", response_model=AiResponseDTO)
async def suggest_next_steps(
    case_id: UUID,
    user: Annotated[CurrentUser, Depends(require_permission("viewCase"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AiResponseDTO:
    case = await _load_case(db, org_id, case_id)
    ctx = await _case_context(db, org_id, case)
    return await _generate_and_log(
        db,
        org_id,
        user.user_id,
        case_id,
        purpose="suggest_next_steps",
        system=(
            "You are a SOC analyst assistant. Recommend the next 3-5 concrete "
            "investigation steps. Be specific. Never recommend destructive actions."
        ),
        user_prompt=f"Case context:\n\n{ctx}\n\nWhat should we do next?",
        provider=None,
        model=None,
    )


@router.post("/freeform", response_model=AiResponseDTO)
async def freeform(
    body: FreeformPayload,
    user: Annotated[CurrentUser, Depends(require_permission("viewCase"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AiResponseDTO:
    prompt = body.prompt
    if body.case_id is not None:
        case = await _load_case(db, org_id, body.case_id)
        ctx = await _case_context(db, org_id, case)
        prompt = f"Case context:\n{ctx}\n\nUser question: {body.prompt}"
    return await _generate_and_log(
        db,
        org_id,
        user.user_id,
        body.case_id,
        purpose="freeform",
        system="You are Adhkar Mind, a SOC analyst assistant. Be precise.",
        user_prompt=prompt,
        provider=body.provider,
        model=body.model,
    )


@router.get("/calls", response_model=list[AiCallDTO])
async def list_calls(
    _user: Annotated[CurrentUser, Depends(require_permission("viewAudit"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
    case_id: UUID | None = None,
    provider: str | None = None,
    since: datetime | None = None,
    limit: int = 100,
) -> list[AiCallDTO]:
    """AI call audit feed. Optional `provider=<name>` scopes to one
    provider (e.g. anthropic/openai); `since=<ISO>` bounds created_at
    for delta polling and cost-window investigations."""
    stmt = select(AiCall).where(AiCall.organization_id == org_id)
    if case_id:
        stmt = stmt.where(AiCall.case_id == case_id)
    if provider is not None:
        stmt = stmt.where(AiCall.provider == provider)
    if since is not None:
        stmt = stmt.where(AiCall.created_at >= since)
    stmt = stmt.order_by(AiCall.created_at.desc()).limit(limit)
    rows = (await db.execute(stmt)).scalars().all()
    return [_to_dto(c) for c in rows]


@router.get("/providers", response_model=list[str])
async def list_providers(
    _user: Annotated[CurrentUser, Depends(require_permission("viewCase"))],
) -> list[str]:
    return get_router().providers()


class AgentPayload(BaseModel):
    prompt: str = Field(min_length=1, max_length=8000)
    provider: str | None = None
    model: str | None = None
    max_steps: int = Field(default=5, ge=1, le=10)


class AgentStepDTO(BaseModel):
    role: str
    content: str
    tool_name: str | None = None
    tool_args: dict[str, Any] | None = None


class AgentRunDTO(BaseModel):
    final_text: str
    tool_calls: int
    steps: list[AgentStepDTO]


@router.post("/agent", response_model=AgentRunDTO)
async def run_tool_use_agent(
    body: AgentPayload,
    user: Annotated[CurrentUser, Depends(require_permission("viewCase"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AgentRunDTO:
    """ToolUse loop. Lets the LLM call Adhkar tools (search_cases,
    get_case, search_observables, search_alerts) up to max_steps times
    while answering the user's question. Every LLM call inside the loop
    is recorded as a separate AiCall row by the underlying router."""
    run = await run_agent(
        db,
        org_id,
        system="You are Adhkar Mind, a SOC assistant. Use tools to ground answers.",
        user_prompt=body.prompt,
        provider=body.provider,
        model=body.model,
        max_steps=body.max_steps,
    )
    db.add(
        AiCall(
            organization_id=org_id,
            user_id=user.user_id,
            case_id=None,
            purpose="agent",
            provider=body.provider or "default",
            model=body.model or "default",
            prompt=body.prompt,
            response_text=run.final_text,
            input_tokens=0,
            output_tokens=0,
            extra={"tool_calls": run.tool_calls, "steps": len(run.steps)},
        )
    )
    await db.flush()
    return AgentRunDTO(
        final_text=run.final_text,
        tool_calls=run.tool_calls,
        steps=[
            AgentStepDTO(
                role=s.role,
                content=s.content,
                tool_name=s.tool_name,
                tool_args=s.tool_args,
            )
            for s in run.steps
        ],
    )
