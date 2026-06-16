"""Shared pytest fixtures."""

import os

import pytest


@pytest.fixture(autouse=True)
def _baseline_env(monkeypatch):
    """Set sane defaults so Settings constructor never aborts in tests."""
    monkeypatch.setenv("ADHKAR_SECRET_KEY", "x" * 32)
    monkeypatch.setenv(
        "DATABASE_URL", os.environ.get("DATABASE_URL", "postgresql+asyncpg://u:p@h/db")
    )
    monkeypatch.setenv("REDIS_URL", os.environ.get("REDIS_URL", "redis://h:6379/0"))
    from adhkar.core.settings import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
