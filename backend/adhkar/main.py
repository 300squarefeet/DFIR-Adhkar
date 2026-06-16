"""FastAPI application factory."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from adhkar import __version__
from adhkar.api.errors import register_exception_handlers
from adhkar.api.v1.api_keys import router as api_keys_router
from adhkar.api.v1.auth import router as auth_router
from adhkar.api.v1.live import router as live_router
from adhkar.api.v1.meta import router as meta_router
from adhkar.api.v1.mfa import router as mfa_router
from adhkar.api.v1.organizations import router as orgs_router
from adhkar.api.v1.profiles import router as profiles_router
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
        from adhkar.workers.outbox_publisher import run_outbox_publisher

        task = asyncio.create_task(run_outbox_publisher(settings))
        try:
            yield
        finally:
            task.cancel()
            try:
                await task
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
    app.include_router(live_router)

    register_exception_handlers(app)
    configure_otel(app, settings)

    return app
