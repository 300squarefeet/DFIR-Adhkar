"""WebSocket live-feed: GET /v1/live (authenticated)."""

from __future__ import annotations

from typing import Annotated

import jwt
import redis.asyncio as redis_async
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, status

from adhkar.api.deps import get_redis, get_settings
from adhkar.auth.jwt import decode_jwt
from adhkar.core.settings import Settings

router = APIRouter(tags=["live"])


@router.websocket("/v1/live")
async def live_feed(
    ws: WebSocket,
    settings: Annotated[Settings, Depends(get_settings)],
    redis: Annotated[redis_async.Redis, Depends(get_redis)],  # type: ignore[type-arg]
) -> None:
    """Subscribe to Redis pub/sub for the user's current organization channel.

    Auth: ?token=<access_jwt> query string OR Authorization Bearer header.
    """
    token = ws.query_params.get("token")
    if not token:
        auth = ws.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[len("Bearer ") :].strip()
    if not token:
        await ws.close(code=status.WS_1008_POLICY_VIOLATION, reason="missing_token")
        return
    try:
        claims = decode_jwt(token, secret=settings.secret_key)
    except jwt.InvalidTokenError:
        await ws.close(code=status.WS_1008_POLICY_VIOLATION, reason="token_invalid")
        return
    if claims.typ != "access":
        await ws.close(code=status.WS_1008_POLICY_VIOLATION, reason="wrong_token_type")
        return
    if not claims.org_id:
        await ws.close(code=status.WS_1008_POLICY_VIOLATION, reason="no_org")
        return

    channel = f"adhkar.events.{claims.org_id}"
    await ws.accept()
    pubsub = redis.pubsub()
    await pubsub.subscribe(channel)
    try:
        async for message in pubsub.listen():
            if message.get("type") != "message":
                continue
            data = message.get("data")
            if isinstance(data, bytes):
                data = data.decode()
            await ws.send_text(str(data))
    except WebSocketDisconnect:
        pass
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.aclose()
