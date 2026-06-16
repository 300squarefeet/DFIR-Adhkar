import pytest
from adhkar.api.errors import register_exception_handlers
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel


class _Payload(BaseModel):
    name: str


@pytest.fixture
def app():
    a = FastAPI()
    register_exception_handlers(a)

    @a.get("/bad-request")
    async def bad() -> None:
        raise HTTPException(status_code=400, detail="nope")

    @a.post("/validate")
    async def validate(_p: _Payload) -> dict[str, str]:
        return {"ok": "yes"}

    @a.get("/boom")
    async def boom() -> None:
        raise RuntimeError("internal explode")

    return a


@pytest.mark.asyncio
async def test_http_exception_translated_to_problem(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.get("/bad-request")
    assert r.status_code == 400
    assert r.headers["content-type"].startswith("application/problem+json")
    body = r.json()
    assert body["type"].startswith("https://adhkar.dev/problems/")
    assert body["title"]
    assert body["status"] == 400
    assert body["detail"] == "nope"
    assert "instance" in body


@pytest.mark.asyncio
async def test_validation_error_translated_to_422_problem(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.post("/validate", json={})  # missing required "name"
    assert r.status_code == 422
    body = r.json()
    assert body["status"] == 422
    assert isinstance(body["errors"], list)
    assert any(e.get("loc") for e in body["errors"])


@pytest.mark.asyncio
async def test_unhandled_exception_returns_500_without_stacktrace(app):
    # raise_app_exceptions=False: Starlette's ServerErrorMiddleware always
    # re-raises after invoking the Exception handler so test clients can opt
    # into seeing it. We opt out — we want the rendered response, not the raise.
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.get("/boom")
    assert r.status_code == 500
    body = r.json()
    assert body["status"] == 500
    assert body["title"] == "Internal Server Error"
    # never leak internals
    assert "Traceback" not in r.text
    assert "RuntimeError" not in r.text
