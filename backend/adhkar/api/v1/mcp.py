"""MCP JSON-RPC 2.0 endpoint."""

from __future__ import annotations

from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from adhkar.api.deps import (
    CurrentUser,
    get_db,
    require_current_org,
    require_permission,
)
from adhkar.db.models import Case, Observable

router = APIRouter(prefix="/v1/mcp", tags=["mcp"])


class JsonRpcRequest(BaseModel):
    jsonrpc: Literal["2.0"]
    id: str | int | None = None
    method: str
    params: dict[str, Any] = Field(default_factory=dict)


class JsonRpcError(BaseModel):
    code: int
    message: str
    data: dict[str, Any] | None = None


class JsonRpcResponse(BaseModel):
    jsonrpc: Literal["2.0"] = "2.0"
    id: str | int | None = None
    result: Any | None = None
    error: JsonRpcError | None = None


TOOLS = [
    {
        "name": "search_cases",
        "description": "List recent cases in the caller's organization.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20},
            },
        },
    },
    {
        "name": "get_case",
        "description": "Fetch a single case by UUID.",
        "inputSchema": {
            "type": "object",
            "properties": {"case_id": {"type": "string"}},
            "required": ["case_id"],
        },
    },
    {
        "name": "search_observables",
        "description": "List observables filtered by data_type / value substring.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "data_type": {"type": "string"},
                "value_contains": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20},
            },
        },
    },
]


async def _list_tools(_org_id: UUID, _db: AsyncSession, _params: dict[str, Any]) -> Any:
    return {"tools": TOOLS}


async def _call_tool(org_id: UUID, db: AsyncSession, params: dict[str, Any]) -> Any:
    name = params.get("name")
    args: dict[str, Any] = params.get("arguments") or {}
    if name == "search_cases":
        limit = int(args.get("limit") or 20)
        rows = (
            (
                await db.execute(
                    select(Case)
                    .where(Case.organization_id == org_id, Case.deleted_at.is_(None))
                    .order_by(Case.number.desc())
                    .limit(min(100, max(1, limit)))
                )
            )
            .scalars()
            .all()
        )
        return {
            "content": [
                {
                    "type": "text",
                    "text": "\n".join(
                        f"#{c.number} {c.title} (sev {c.severity}, {c.stage})" for c in rows
                    )
                    or "(no cases)",
                }
            ]
        }
    if name == "get_case":
        try:
            cid = UUID(str(args.get("case_id") or ""))
        except ValueError as e:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid_case_id") from e
        c = (
            await db.execute(
                select(Case).where(
                    Case.id == cid,
                    Case.organization_id == org_id,
                    Case.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if not c:
            return {"content": [{"type": "text", "text": "case_not_found"}], "isError": True}
        return {
            "content": [
                {
                    "type": "text",
                    "text": (
                        f"#{c.number} {c.title}\n"
                        f"Severity: {c.severity}  TLP: {c.tlp}  Stage: {c.stage}\n"
                        f"Description: {c.description or '(none)'}"
                    ),
                }
            ]
        }
    if name == "search_observables":
        data_type = str(args.get("data_type") or "")
        contains = str(args.get("value_contains") or "")
        limit = int(args.get("limit") or 20)
        ostmt = select(Observable).where(
            Observable.organization_id == org_id, Observable.deleted_at.is_(None)
        )
        if data_type:
            ostmt = ostmt.where(Observable.data_type == data_type)
        if contains:
            ostmt = ostmt.where(Observable.data.ilike(f"%{contains}%"))
        observables = (await db.execute(ostmt.limit(min(100, max(1, limit))))).scalars().all()
        return {
            "content": [
                {
                    "type": "text",
                    "text": "\n".join(f"{o.data_type}: {o.data}" for o in observables) or "(none)",
                }
            ]
        }
    raise HTTPException(status.HTTP_400_BAD_REQUEST, f"unknown_tool:{name}")


_METHODS = {
    "tools/list": _list_tools,
    "tools/call": _call_tool,
}


@router.post("/rpc", response_model=JsonRpcResponse)
async def rpc(
    body: JsonRpcRequest,
    _user: Annotated[CurrentUser, Depends(require_permission("viewCase"))],
    org_id: Annotated[UUID, Depends(require_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JsonRpcResponse:
    handler = _METHODS.get(body.method)
    if handler is None:
        return JsonRpcResponse(
            id=body.id, error=JsonRpcError(code=-32601, message="method_not_found")
        )
    try:
        result = await handler(org_id, db, body.params)
        return JsonRpcResponse(id=body.id, result=result)
    except HTTPException as e:
        return JsonRpcResponse(
            id=body.id,
            error=JsonRpcError(code=-32602, message=str(e.detail)),
        )
