"""saml_replay.mark_seen — fakeredis-backed tests."""

from __future__ import annotations

import asyncio

import fakeredis.aioredis
import pytest
import pytest_asyncio
from adhkar.auth.saml_replay import mark_seen


@pytest_asyncio.fixture
async def redis() -> fakeredis.aioredis.FakeRedis:
    r = fakeredis.aioredis.FakeRedis()
    try:
        yield r
    finally:
        await r.aclose()


@pytest.mark.asyncio
async def test_mark_seen_returns_true_first_time(redis) -> None:
    assert await mark_seen(redis, "assertion-id-1", ttl_seconds=300) is True


@pytest.mark.asyncio
async def test_mark_seen_returns_false_on_replay(redis) -> None:
    await mark_seen(redis, "assertion-id-2", ttl_seconds=300)
    assert await mark_seen(redis, "assertion-id-2", ttl_seconds=300) is False


@pytest.mark.asyncio
async def test_mark_seen_clamps_ttl_lower_bound(redis) -> None:
    assert await mark_seen(redis, "assertion-id-3", ttl_seconds=0) is True
    # After clamp to 1s the key exists.
    assert await redis.exists("saml:seen:assertion-id-3") == 1


@pytest.mark.asyncio
async def test_mark_seen_clamps_ttl_upper_bound(redis) -> None:
    await mark_seen(redis, "assertion-id-4", ttl_seconds=999_999)
    ttl = await redis.ttl("saml:seen:assertion-id-4")
    assert 0 < ttl <= 86400


@pytest.mark.asyncio
async def test_mark_seen_respects_ttl_expiry(redis) -> None:
    await mark_seen(redis, "assertion-id-5", ttl_seconds=1)
    await asyncio.sleep(1.1)
    # After TTL elapses the second mark_seen should also return True.
    assert await mark_seen(redis, "assertion-id-5", ttl_seconds=300) is True
