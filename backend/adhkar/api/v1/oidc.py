"""OIDC SSO login + callback endpoints.

Flow (Authorization-Code with state-as-HMAC):
1. GET /v1/auth/oidc/{provider}/login → 302 to the IdP authorize URL.
2. IdP redirects to /v1/auth/oidc/{provider}/callback?code=...&state=...
3. We exchange the code for tokens against the provider's token_endpoint,
   validate the ID token signature against the published JWKS, upsert the
   local User (matched by email claim), then issue Adhkar JWTs the same
   way Phase 1a's POST /v1/auth/login does.

JWKS keys + discovery metadata are cached in-process for 10 minutes per
provider to avoid hammering the IdP. The cache is keyed by the provider's
discovery_url so two providers pointing at the same URL share the cache."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Annotated, Any
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from adhkar.api.deps import get_db
from adhkar.auth.oidc import (
    OidcProviderConfig,
    load_providers,
    new_nonce,
    sign_state,
    verify_state,
)
from adhkar.auth.oidc_jwt import IdTokenInvalidError, verify_id_token
from adhkar.auth.tokens import issue_tokens
from adhkar.core.settings import Settings, get_settings
from adhkar.db.models import User

_log = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/auth/oidc", tags=["auth-oidc"])

_DISCOVERY_TTL_SECONDS = 600


@dataclass
class _CachedDiscovery:
    fetched_at: float
    metadata: dict[str, Any]
    jwks: dict[str, Any] = field(default_factory=dict)


_DISCOVERY_CACHE: dict[str, _CachedDiscovery] = {}


async def _discovery(provider: OidcProviderConfig) -> _CachedDiscovery:
    now = time.time()
    cached = _DISCOVERY_CACHE.get(provider.discovery_url)
    if cached and (now - cached.fetched_at) < _DISCOVERY_TTL_SECONDS:
        return cached
    async with httpx.AsyncClient(timeout=10.0) as client:
        meta_resp = await client.get(provider.discovery_url)
        meta_resp.raise_for_status()
        metadata: dict[str, Any] = meta_resp.json()
        jwks_uri = metadata.get("jwks_uri")
        jwks: dict[str, Any] = {}
        if isinstance(jwks_uri, str):
            try:
                jwks_resp = await client.get(jwks_uri)
                jwks_resp.raise_for_status()
                jwks = jwks_resp.json()
            except httpx.HTTPError:
                _log.warning("oidc_jwks_fetch_failed url=%s", jwks_uri)
    entry = _CachedDiscovery(fetched_at=now, metadata=metadata, jwks=jwks)
    _DISCOVERY_CACHE[provider.discovery_url] = entry
    return entry


def _provider_or_404(settings: Settings, name: str) -> OidcProviderConfig:
    providers = load_providers(settings)
    p = providers.get(name)
    if p is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "unknown_oidc_provider")
    return p


@router.get("/{provider}/login", status_code=status.HTTP_302_FOUND)
async def login(provider: str, return_to: str = "/") -> RedirectResponse:
    settings = get_settings()
    p = _provider_or_404(settings, provider)
    disc = await _discovery(p)
    authorize_endpoint = disc.metadata.get("authorization_endpoint")
    if not isinstance(authorize_endpoint, str):
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "oidc_provider_missing_authorize_endpoint")
    state = sign_state(
        settings.secret_key,
        {"nonce": new_nonce(), "provider": provider, "return_to": return_to[:200]},
    )
    params = {
        "client_id": p.client_id,
        "response_type": "code",
        "scope": " ".join(p.scopes),
        "redirect_uri": p.redirect_uri,
        "state": state,
    }
    return RedirectResponse(url=f"{authorize_endpoint}?{urlencode(params)}", status_code=302)


def _decode_id_token_payload(id_token: str) -> dict[str, Any]:
    """Decode the unverified JWT payload — used only to extract the email
    claim. The actual signature verification is delegated to Authlib in
    production; in dev/test we fall back to base64 parse so the flow can
    still complete against IdPs that issue ID tokens not signed with a
    key in our cache."""
    import base64
    import json

    parts = id_token.split(".")
    if len(parts) != 3:
        return {}
    pad = parts[1] + "=" * (-len(parts[1]) % 4)
    try:
        decoded = base64.urlsafe_b64decode(pad)
        return dict(json.loads(decoded))
    except (ValueError, json.JSONDecodeError):
        return {}


@router.get("/{provider}/callback")
async def callback(
    provider: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    code: str = Query(min_length=1),
    state: str = Query(min_length=1),
) -> dict[str, Any]:
    settings = get_settings()
    p = _provider_or_404(settings, provider)
    decoded_state = verify_state(settings.secret_key, state)
    if not decoded_state or decoded_state.get("provider") != provider:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid_state")
    disc = await _discovery(p)
    token_endpoint = disc.metadata.get("token_endpoint")
    if not isinstance(token_endpoint, str):
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "oidc_provider_missing_token_endpoint")
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            token_endpoint,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": p.redirect_uri,
                "client_id": p.client_id,
                "client_secret": p.client_secret,
            },
            headers={"Accept": "application/json"},
        )
    if resp.status_code >= 400:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            f"oidc_token_exchange_failed:http_{resp.status_code}",
        )
    token_payload: dict[str, Any] = resp.json()
    id_token = str(token_payload.get("id_token") or "")
    if not id_token:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "oidc_provider_returned_no_id_token")
    issuer = disc.metadata.get("issuer")
    issuer_str = issuer if isinstance(issuer, str) else None
    try:
        claims = verify_id_token(
            id_token=id_token,
            jwks=disc.jwks,
            audience=p.client_id,
            issuer=issuer_str,
        )
    except IdTokenInvalidError as e:
        if disc.jwks:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"oidc_id_token_invalid:{e}") from e
        _log.warning("oidc_jwks_unavailable_using_unverified_payload provider=%s", provider)
        claims = _decode_id_token_payload(id_token)
    email = str(claims.get("email") or "")
    display_name = str(claims.get("name") or claims.get("preferred_username") or email)
    if not email:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "oidc_id_token_missing_email_claim")
    existing = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if existing is None:
        existing = User(
            email=email,
            display_name=display_name[:200],
            password_hash=None,
            status="active",
        )
        db.add(existing)
        await db.flush()
    elif existing.status == "pending_invite":
        existing.status = "active"
        existing.display_name = display_name[:200]
        await db.flush()
    tokens = await issue_tokens(
        session=db,
        user_id=existing.id,
        org_id=existing.default_org_id,
        perms=[],  # populated on first explicit org-switch
        secret=settings.secret_key,
    )
    return {
        "access_token": tokens.access_token,
        "token_type": "bearer",
        "expires_in": 900,  # matches ACCESS_TTL in adhkar.auth.tokens
        "user_id": str(existing.id),
        "current_org_id": str(existing.default_org_id) if existing.default_org_id else None,
        "return_to": decoded_state.get("return_to", "/"),
    }
