from unittest.mock import AsyncMock, MagicMock

import pytest
from adhkar.db.readiness import CheckResult, check_redis, check_s3


@pytest.mark.asyncio
async def test_check_redis_ok():
    fake = AsyncMock()
    fake.ping.return_value = True
    result = await check_redis(fake)
    assert result == CheckResult(name="redis", ok=True, detail=None)


@pytest.mark.asyncio
async def test_check_redis_down():
    fake = AsyncMock()
    fake.ping.side_effect = ConnectionError("nope")
    result = await check_redis(fake)
    assert result.ok is False
    assert result.name == "redis"
    assert "nope" in (result.detail or "")


@pytest.mark.asyncio
async def test_check_s3_ok():
    client = MagicMock()
    client.head_bucket = MagicMock(return_value={"ResponseMetadata": {"HTTPStatusCode": 200}})
    result = await check_s3(client, bucket="adhkar-attachments")
    assert result == CheckResult(name="s3", ok=True, detail=None)


@pytest.mark.asyncio
async def test_check_s3_missing_bucket():
    client = MagicMock()
    client.head_bucket = MagicMock(side_effect=Exception("NoSuchBucket"))
    result = await check_s3(client, bucket="adhkar-attachments")
    assert result.ok is False
    assert "NoSuchBucket" in (result.detail or "")
