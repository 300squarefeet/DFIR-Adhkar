"""FastAPI application factory."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from adhkar import __version__
from adhkar.api.errors import register_exception_handlers
from adhkar.api.v1.auth import router as auth_router
from adhkar.api.v1.meta import router as meta_router
from adhkar.core.logging import configure_logging
from adhkar.core.middleware import AccessLogMiddleware, RequestIdMiddleware
from adhkar.core.otel import configure_otel
from adhkar.core.settings import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings)

    app = FastAPI(
        title="Adhkar IR API",
        version=__version__,
        openapi_url="/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
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
    register_exception_handlers(app)
    configure_otel(app, settings)

    return app
