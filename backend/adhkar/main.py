"""FastAPI application factory."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from adhkar import __version__
from adhkar.api.errors import register_exception_handlers
from adhkar.api.v1.alerts import router as alerts_router
from adhkar.api.v1.analyzer_jobs import router as analyzer_jobs_router
from adhkar.api.v1.api_keys import router as api_keys_router
from adhkar.api.v1.audit import router as audit_router
from adhkar.api.v1.auth import router as auth_router
from adhkar.api.v1.case_comments import router as case_comments_router
from adhkar.api.v1.cases import router as cases_router
from adhkar.api.v1.kb import router as kb_router
from adhkar.api.v1.live import router as live_router
from adhkar.api.v1.meta import router as meta_router
from adhkar.api.v1.mfa import router as mfa_router
from adhkar.api.v1.observables import router as observables_router
from adhkar.api.v1.organizations import router as orgs_router
from adhkar.api.v1.profiles import router as profiles_router
from adhkar.api.v1.ttps import router as ttps_router
from adhkar.api.v1.users import router as users_router
from adhkar.core.logging import configure_logging
from adhkar.core.middleware import AccessLogMiddleware, RequestIdMiddleware
from adhkar.core.otel import configure_otel
from adhkar.core.settings import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        from adhkar.workers.analyzer_runner import run_analyzer_runner
        from adhkar.workers.outbox_publisher import run_outbox_publisher

        outbox = asyncio.create_task(run_outbox_publisher(settings))
        analyzer = asyncio.create_task(run_analyzer_runner(settings))
        try:
            yield
        finally:
            for t in (outbox, analyzer):
                t.cancel()
            for t in (outbox, analyzer):
                try:
                    await t
                except (asyncio.CancelledError, Exception):  # noqa: S110
                    pass

    app = FastAPI(
        title="Adhkar IR API",
        version=__version__,
        openapi_url="/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    app.add_middleware(AccessLogMiddleware)
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-Id"],
    )

    app.include_router(meta_router)
    app.include_router(auth_router)
    app.include_router(users_router)
    app.include_router(mfa_router)
    app.include_router(orgs_router)
    app.include_router(profiles_router)
    app.include_router(api_keys_router)
    app.include_router(audit_router)
    app.include_router(observables_router)
    app.include_router(analyzer_jobs_router)
    app.include_router(cases_router)
    app.include_router(case_comments_router)
    app.include_router(alerts_router)
    app.include_router(ttps_router)
    app.include_router(kb_router)
    app.include_router(live_router)

    register_exception_handlers(app)
    configure_otel(app, settings)

    return app
