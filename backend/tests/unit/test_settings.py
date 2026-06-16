import pytest
from adhkar.core.settings import Settings
from pydantic import ValidationError


def test_settings_loads_with_defaults_when_secret_provided(monkeypatch):
    monkeypatch.setenv("ADHKAR_SECRET_KEY", "x" * 32)
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h/db")
    monkeypatch.setenv("REDIS_URL", "redis://h:6379/0")
    s = Settings()
    assert s.env == "dev"
    assert s.log_level == "INFO"
    assert s.s3_bucket == "adhkar-attachments"
    assert s.s3_region == "us-east-1"
    assert s.otel_exporter_otlp_endpoint == ""
    assert s.otel_service_name == "adhkar-api"


def test_settings_rejects_short_secret_key(monkeypatch):
    monkeypatch.setenv("ADHKAR_SECRET_KEY", "too-short")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h/db")
    monkeypatch.setenv("REDIS_URL", "redis://h:6379/0")
    with pytest.raises(ValidationError) as excinfo:
        Settings()
    assert "at least 32 characters" in str(excinfo.value)


def test_settings_reads_adhkar_prefixed_env(monkeypatch):
    monkeypatch.setenv("ADHKAR_SECRET_KEY", "x" * 32)
    monkeypatch.setenv("ADHKAR_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("ADHKAR_S3_BUCKET", "custom-bucket")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h/db")
    monkeypatch.setenv("REDIS_URL", "redis://h:6379/0")
    s = Settings()
    assert s.log_level == "DEBUG"
    assert s.s3_bucket == "custom-bucket"
