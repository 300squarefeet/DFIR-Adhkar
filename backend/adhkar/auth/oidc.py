"""OIDC SSO provider integration via Authlib.

Login flow:
  1. GET /v1/auth/oidc/{provider}/login → redirects to the IdP authorize URL
  2. IdP redirects back to /v1/auth/oidc/{provider}/callback?code=...
  3. We exchange the code for tokens, validate the ID token, upsert the
     local User, issue Adhkar JWTs (the same shape Phase 1a login emits).

Providers are configured via Settings.oidc_providers (a dict keyed by
provider name → {client_id, client_secret, discovery_url, scopes}). The
state parameter is HMAC-signed with ADHKAR_SECRET_KEY to defeat CSRF
without a server-side session.

Multi-tenancy: a new SSO user lands in NO org by default; the org admin
attaches them to an org via the existing user-admin endpoints. This
matches the brief's 'profiles + multi-tenancy not retrofitted' rule —
we never auto-grant org access on SSO login."""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass

from adhkar.core.settings import Settings


@dataclass(frozen=True, slots=True)
class OidcProviderConfig:
    name: str
    client_id: str
    client_secret: str
    discovery_url: str
    scopes: tuple[str, ...] = ("openid", "email", "profile")
    redirect_uri: str = ""


def sign_state(secret: str, state: dict[str, str]) -> str:
    """Encode + HMAC the state payload so the callback can verify the
    flow originated here."""
    body = json.dumps(state, separators=(",", ":"), sort_keys=True)
    mac = hmac.new(secret.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{body}|{mac}"


def verify_state(secret: str, encoded: str) -> dict[str, str] | None:
    """Return the decoded state if its MAC matches, else None."""
    if "|" not in encoded:
        return None
    body, mac = encoded.rsplit("|", 1)
    expected = hmac.new(secret.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(mac, expected):
        return None
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    return {str(k): str(v) for k, v in parsed.items()}


def new_nonce() -> str:
    return secrets.token_urlsafe(24)


def load_providers(settings: Settings) -> dict[str, OidcProviderConfig]:
    """Parse `settings.oidc_providers_json` (a JSON-encoded mapping)."""
    raw = settings.oidc_providers_json or ""
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(parsed, dict):
        return {}
    out: dict[str, OidcProviderConfig] = {}
    for name, cfg in parsed.items():
        if not isinstance(cfg, dict):
            continue
        cid = cfg.get("client_id")
        cs = cfg.get("client_secret")
        dl = cfg.get("discovery_url")
        if not (isinstance(cid, str) and isinstance(cs, str) and isinstance(dl, str)):
            continue
        scopes = tuple(
            s for s in cfg.get("scopes", ["openid", "email", "profile"]) if isinstance(s, str)
        ) or ("openid", "email", "profile")
        out[str(name)] = OidcProviderConfig(
            name=str(name),
            client_id=cid,
            client_secret=cs,
            discovery_url=dl,
            scopes=scopes,
            redirect_uri=str(cfg.get("redirect_uri", "")),
        )
    return out
