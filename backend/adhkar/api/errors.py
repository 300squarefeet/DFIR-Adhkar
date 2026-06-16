"""RFC 7807 problem+json exception handlers."""

from typing import Any

import structlog
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from adhkar.core.logging import get_request_id

_PROBLEM_BASE = "https://adhkar.dev/problems/"


def _problem(
    *,
    slug: str,
    title: str,
    http_status: int,
    detail: str,
    extra: dict[str, Any] | None = None,
) -> JSONResponse:
    body: dict[str, Any] = {
        "type": f"{_PROBLEM_BASE}{slug}",
        "title": title,
        "status": http_status,
        "detail": detail,
        "instance": get_request_id(),
    }
    if extra:
        body.update(extra)
    return JSONResponse(
        status_code=http_status,
        content=body,
        media_type="application/problem+json",
    )


async def _http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
    return _problem(
        slug=f"http-{exc.status_code}",
        title=_title_for(exc.status_code),
        http_status=exc.status_code,
        detail=str(exc.detail),
    )


async def _validation_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = [
        {"loc": list(e.get("loc", [])), "msg": e.get("msg", ""), "type": e.get("type", "")}
        for e in exc.errors()
    ]
    return _problem(
        slug="validation",
        title="Unprocessable Entity",
        http_status=422,
        detail="Request validation failed",
        extra={"errors": errors},
    )


async def _unhandled_handler(_request: Request, exc: Exception) -> JSONResponse:
    # Log defensively: never let a structlog hiccup empty out the error response.
    # (See history: writing through the module-level cached logger after another
    # test reconfigured structlog could swallow the JSONResponse body under some
    # test orderings. The response body is the contract; logging is best-effort.)
    try:
        structlog.get_logger().error("unhandled_exception", exc_type=type(exc).__name__)
    except Exception:  # noqa: BLE001 — logging must never break error responses
        pass
    return _problem(
        slug="internal",
        title="Internal Server Error",
        http_status=500,
        detail=(
            "An internal error occurred. Please retry; if this persists, contact the administrator."
        ),
    )


def _title_for(code: int) -> str:
    return {
        400: "Bad Request",
        401: "Unauthorized",
        403: "Forbidden",
        404: "Not Found",
        405: "Method Not Allowed",
        409: "Conflict",
        422: "Unprocessable Entity",
        429: "Too Many Requests",
    }.get(code, "Error")


def register_exception_handlers(app: FastAPI) -> None:
    # Starlette's add_exception_handler expects handlers typed against the
    # base Exception, but ours are typed against the specific subclass for
    # clarity. This is structurally safe — the dispatcher only calls each
    # handler with an instance of its registered class.
    app.add_exception_handler(HTTPException, _http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, _validation_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, _unhandled_handler)
