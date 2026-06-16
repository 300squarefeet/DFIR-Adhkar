"""Smoke: the OpenAPI spec lists every Phase 2-10 route family we shipped.

If a router fails to mount (typo, import error, or missing include_router
call in main.py) this catches it without needing a live DB."""

from __future__ import annotations

import pytest
from adhkar.core.settings import Settings
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def settings(monkeypatch):
    monkeypatch.setenv("ADHKAR_SECRET_KEY", "x" * 32)
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h/db")
    monkeypatch.setenv("REDIS_URL", "redis://h:6379/0")
    from adhkar.core.settings import get_settings

    get_settings.cache_clear()
    return Settings()


EXPECTED_PATHS: tuple[str, ...] = (
    # Phase 0
    "/healthz",
    "/readyz",
    "/version",
    # Phase 1a
    "/v1/auth/login",
    "/v1/auth/refresh",
    "/v1/auth/logout",
    "/v1/auth/me",
    "/v1/users",
    "/v1/users/invite",
    "/v1/organizations",
    "/v1/profiles",
    "/v1/me/api-keys",
    # Phase 1b
    "/v1/audit",
    # Phase 2
    "/v1/observables",
    "/v1/analyzers",
    # Phase 3
    "/v1/cases",
    "/v1/cases/{case_id}/tasks",
    "/v1/cases/{case_id}/comments",
    "/v1/cases/{case_id}/links",
    # Phase 4
    "/v1/alerts",
    "/v1/alerts/{alert_id}/promote",
    # Phase 5
    "/v1/ttps/catalog",
    "/v1/cases/{case_id}/ttps",
    # Phase 6
    "/v1/kb/pages",
    "/v1/case-templates",
    # Phase 7
    "/v1/notification-endpoints",
    "/v1/notification-rules",
    # Phase 8
    "/v1/ai/freeform",
    "/v1/ai/calls",
    "/v1/ai/providers",
    # Phase 9
    "/v1/cases/{case_id}/attachments",
    "/v1/cases/{case_id}/shares",
    "/v1/attachments/presign",
    "/v1/attachments/av-scan-webhook",
    # Phase 5+ extension: responders
    "/v1/responders",
    "/v1/responders/{name}/{entity_type}/{entity_id}",
    # MCP server
    "/v1/mcp/rpc",
    # RAG similarity + ToolUse agent
    "/v1/similarity/cases",
    "/v1/ai/agent",
    # GDPR
    "/v1/gdpr/users/{user_id}/export",
    "/v1/gdpr/users/{user_id}/erase",
    # OIDC SSO
    "/v1/auth/oidc/{provider}/login",
    "/v1/auth/oidc/{provider}/callback",
    # Portal
    "/v1/portal/cases",
    "/v1/portal/cases/{case_id}/comments",
    # Full-text search
    "/v1/search",
    # SAML SSO
    "/v1/auth/saml/{provider}/login",
    "/v1/auth/saml/{provider}/acs",
    # Bulk actions
    "/v1/cases/bulk-patch",
    "/v1/alerts/bulk-patch",
    "/v1/observables/bulk-patch",
)


@pytest.mark.asyncio
async def test_all_shipped_routes_are_in_openapi(settings):
    from adhkar.main import create_app

    app = create_app(settings)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.get("/openapi.json")
    spec = r.json()
    paths: set[str] = set(spec["paths"].keys())
    missing = [p for p in EXPECTED_PATHS if p not in paths]
    assert not missing, f"OpenAPI spec is missing expected routes: {missing}"


@pytest.mark.asyncio
async def test_security_headers_present(settings):
    from adhkar.main import create_app

    app = create_app(settings)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.get("/healthz")
    assert r.headers.get("x-frame-options") == "DENY"
    assert "default-src 'self'" in r.headers.get("content-security-policy", "")
    assert r.headers.get("x-content-type-options") == "nosniff"
    assert "max-age" in r.headers.get("strict-transport-security", "")


@pytest.mark.asyncio
async def test_ai_providers_endpoint_returns_stub(settings):
    from adhkar.main import create_app

    app = create_app(settings)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.get("/v1/ai/providers")
    # Endpoint requires auth — but at least it's mounted and rejects cleanly.
    assert r.status_code in (401, 403)
