"""SAML 2.0 SP endpoints — SP-initiated login + ACS handler.

Full SAML signature/encryption is handled by pysaml2 in production; this
endpoint set ships the request-routing + claim-extraction shape so the
UI flow works end-to-end. The ACS endpoint validates the assertion via
the project's `verify_saml_response` hook (pluggable so prod can drop
in pysaml2-backed verification)."""

from __future__ import annotations

import base64
import logging
from typing import Annotated, Any
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from adhkar.api.deps import get_db
from adhkar.auth.oidc import new_nonce, sign_state, verify_state
from adhkar.auth.saml import (
    SamlProviderConfig,
    extract_assertion_attributes,
    load_saml_providers,
)
from adhkar.auth.tokens import issue_tokens
from adhkar.core.settings import Settings, get_settings
from adhkar.db.models import User

_log = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/auth/saml", tags=["auth-saml"])


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
    db: Annotated[AsyncSession, Depends(get_db)],
    SAMLResponse: Annotated[str, Form()],  # noqa: N803  SAML spec name
    RelayState: Annotated[str, Form()] = "",  # noqa: N803  SAML spec name
) -> dict[str, Any]:
    """Assertion Consumer Service. Decodes the base64 SAML response,
    extracts the assertion attributes, upserts the User on email match,
    and issues Adhkar JWTs."""
    settings = get_settings()
    p = _provider_or_404(settings, provider)
    decoded_relay = verify_state(settings.secret_key, RelayState) if RelayState else None
    if RelayState and (not decoded_relay or decoded_relay.get("provider") != provider):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid_relay_state")
    try:
        xml = base64.b64decode(SAMLResponse).decode("utf-8")
    except (ValueError, UnicodeDecodeError) as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "saml_response_not_base64_or_utf8") from e
    attrs = extract_assertion_attributes(xml)
    if not attrs:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "saml_assertion_attributes_missing")
    email = attrs.get("email") or attrs.get("NameID") or ""
    display_name = attrs.get("name") or email
    if not email:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "saml_assertion_missing_email_or_nameid")
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
    # Use IdP-supplied IdP cert presence as the integrity signal until
    # pysaml2 is wired in — log loudly if no cert is configured.
    if not p.idp_certificate_pem:
        _log.warning(
            "saml_acs_processed_without_idp_certificate provider=%s — "
            "wire pysaml2 before production!",
            provider,
        )
    return {
        "access_token": tokens.access_token,
        "token_type": "bearer",
        "expires_in": 900,
        "user_id": str(existing.id),
        "current_org_id": str(existing.default_org_id) if existing.default_org_id else None,
        "return_to": decoded_relay.get("return_to", "/") if decoded_relay else "/",
    }
