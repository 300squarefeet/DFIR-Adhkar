"""SAML 2.0 SP endpoints — SP-initiated login + ACS handler.

Full SAML signature/encryption is handled by pysaml2 in production; this
endpoint set ships the request-routing + claim-extraction shape so the
UI flow works end-to-end. The ACS endpoint validates the assertion via
the project's `verify_saml_response` hook (pluggable so prod can drop
in pysaml2-backed verification)."""

from __future__ import annotations

import logging
from typing import Annotated, Any
from urllib.parse import urlencode

import redis.asyncio as redis_async
from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from adhkar.api.deps import get_db, get_redis
from adhkar.auth.oidc import new_nonce, sign_state, verify_state
from adhkar.auth.saml import SamlProviderConfig, load_saml_providers
from adhkar.auth.saml_errors import (
    SamlAudienceError,
    SamlConfigError,
    SamlRecipientError,
    SamlReplayError,
    SamlSignatureError,
    SamlTimingError,
)
from adhkar.auth.tokens import issue_tokens
from adhkar.core.settings import Settings, get_settings
from adhkar.db.models import User

router = APIRouter(prefix="/v1/auth/saml", tags=["auth-saml"])

_log = logging.getLogger(__name__)


def _provider_or_404(settings: Settings, name: str) -> SamlProviderConfig:
    providers = load_saml_providers(settings)
    p = providers.get(name)
    if p is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "unknown_saml_provider")
    return p


@router.get("/{provider}/login", status_code=status.HTTP_302_FOUND)
async def login(provider: str, return_to: str = "/") -> RedirectResponse:
    """SP-initiated SAML login: redirect to IdP SSO URL with RelayState."""
    settings = get_settings()
    p = _provider_or_404(settings, provider)
    relay = sign_state(
        settings.secret_key,
        {"nonce": new_nonce(), "provider": provider, "return_to": return_to[:200]},
    )
    # IdP-side AuthnRequest construction is delegated to pysaml2 in
    # production; here we just hand the IdP a RelayState in the simplest
    # possible form so the round trip works in dev with reflector IdPs.
    return RedirectResponse(
        url=f"{p.idp_sso_url}?{urlencode({'RelayState': relay})}", status_code=302
    )


@router.post("/{provider}/acs")
async def acs(
    provider: str,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[redis_async.Redis, Depends(get_redis)],  # type: ignore[type-arg]
    SAMLResponse: Annotated[str, Form()],  # noqa: N803  SAML spec name
    RelayState: Annotated[str, Form()] = "",  # noqa: N803  SAML spec name
) -> dict[str, Any]:
    """Assertion Consumer Service. Verifies SAML signature/audience/
    recipient/timing/replay via pysaml2-backed SamlVerifier, upserts
    the User on email match, and issues Adhkar JWTs."""
    settings = get_settings()
    _provider_or_404(settings, provider)
    decoded_relay = verify_state(settings.secret_key, RelayState) if RelayState else None
    if RelayState and (not decoded_relay or decoded_relay.get("provider") != provider):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid_relay_state")

    verifier = getattr(request.app.state, "saml_verifiers", {}).get(provider)
    if verifier is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "saml_metadata_unavailable")

    try:
        claims = await verifier.verify_and_extract(SAMLResponse, redis=redis)
    except SamlSignatureError as e:
        await _audit_failed(db, provider, "signature_invalid", e.reason, request)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "signature_invalid") from e
    except SamlTimingError as e:
        await _audit_failed(db, provider, "assertion_expired", e.reason, request)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "assertion_expired") from e
    except SamlAudienceError as e:
        await _audit_failed(db, provider, "audience_mismatch", e.reason, request)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "audience_mismatch") from e
    except SamlRecipientError as e:
        await _audit_failed(db, provider, "recipient_mismatch", e.reason, request)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "recipient_mismatch") from e
    except SamlReplayError as e:
        await _audit_failed(db, provider, "assertion_replayed", e.reason, request)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "assertion_replayed") from e
    except SamlConfigError as e:
        await _audit_failed(db, provider, "saml_misconfigured", e.reason, request)
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "saml_misconfigured") from e

    email = (claims.email or claims.name_id or "").strip()
    if not email:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "saml_assertion_missing_email_or_nameid")
    display_name = claims.display_name or email
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
        perms=[],
        secret=settings.secret_key,
    )
    return {
        "access_token": tokens.access_token,
        "token_type": "bearer",
        "expires_in": 900,
        "user_id": str(existing.id),
        "current_org_id": str(existing.default_org_id) if existing.default_org_id else None,
        "return_to": decoded_relay.get("return_to", "/") if decoded_relay else "/",
    }


async def _audit_failed(
    db: AsyncSession,
    provider: str,
    code: str,
    reason: str,
    request: Request,
) -> None:
    from adhkar.audit import audit_and_emit

    try:
        await audit_and_emit(
            db,
            actor_user_id=None,
            organization_id=None,
            action="saml_verify_failed",
            entity_type="user",
            entity_id=None,
            diff={
                "provider": provider,
                "code": code,
                "reason": reason,
                "source_ip": (request.client.host if request.client else None),
            },
        )
    except Exception:
        _log.exception(
            "saml_audit_emit_failed provider=%s code=%s reason=%s",
            provider,
            code,
            reason,
        )
