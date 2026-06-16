import json

import pytest
import structlog
from adhkar.core.logging import configure_logging
from adhkar.core.settings import Settings


@pytest.fixture
def settings(monkeypatch):
    monkeypatch.setenv("ADHKAR_SECRET_KEY", "x" * 32)
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h/db")
    monkeypatch.setenv("REDIS_URL", "redis://h:6379/0")
    monkeypatch.setenv("ADHKAR_LOG_LEVEL", "INFO")
    return Settings()


def test_log_output_is_json_with_required_fields(settings, capsys):
    configure_logging(settings)
    log = structlog.get_logger()
    log.info("user_logged_in", user_id="abc")
    captured = capsys.readouterr().out.strip().splitlines()[-1]
    payload = json.loads(captured)
    assert payload["event"] == "user_logged_in"
    assert payload["user_id"] == "abc"
    assert payload["level"] == "info"
    assert "ts" in payload
    # request_id is bound by middleware; here it should default to empty string
    assert "request_id" in payload


def test_log_level_threshold_respected(settings, capsys, monkeypatch):
    monkeypatch.setenv("ADHKAR_LOG_LEVEL", "WARNING")
    settings = Settings()
    configure_logging(settings)
    log = structlog.get_logger()
    log.info("should_be_dropped")
    log.warning("should_be_kept")
    out = capsys.readouterr().out
    assert "should_be_dropped" not in out
    assert "should_be_kept" in out
