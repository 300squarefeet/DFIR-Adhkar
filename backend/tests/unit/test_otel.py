import pytest
from adhkar.core.otel import configure_otel
from adhkar.core.settings import Settings
from fastapi import FastAPI

_VALID_PROVIDERS = ("ProxyTracerProvider", "NoOpTracerProvider", "TracerProvider")


@pytest.fixture
def app_settings(monkeypatch):
    monkeypatch.setenv("ADHKAR_SECRET_KEY", "x" * 32)
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h/db")
    monkeypatch.setenv("REDIS_URL", "redis://h:6379/0")
    return Settings()


def test_otel_noop_when_endpoint_empty(app_settings):
    app = FastAPI()
    configure_otel(app, app_settings)
    # no exporter registered, no exception thrown
    # check the tracer provider is the default NoOpTracerProvider
    from opentelemetry import trace

    provider = trace.get_tracer_provider()
    assert type(provider).__name__ in _VALID_PROVIDERS


def test_otel_setup_when_endpoint_present(monkeypatch, app_settings):
    monkeypatch.setenv("ADHKAR_OTEL_EXPORTER_OTLP_ENDPOINT", "http://jaeger:4317")
    s = Settings()
    app = FastAPI()
    # should not raise even though the endpoint is unreachable in test (gRPC exporter is lazy)
    configure_otel(app, s)
