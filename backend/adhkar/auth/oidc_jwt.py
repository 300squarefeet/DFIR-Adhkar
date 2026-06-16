"""OIDC ID-token signature + claims verification via Authlib.

The OIDC callback path lifts the email/name out of the ID token. Without
signature verification, a hostile IdP (or an attacker who controls the
redirect) could mint a fake ID token that authenticates as any user.

Verification is split out so the callback can choose between strict mode
(production) and lenient mode (dev, when the IdP's JWKS isn't reachable
from the test environment)."""

from __future__ import annotations

import logging
import time
from typing import Any

from authlib.jose import JsonWebKey, JsonWebToken  # type: ignore[import-untyped]
from authlib.jose.errors import JoseError  # type: ignore[import-untyped]

_log = logging.getLogger(__name__)


class IdTokenInvalidError(Exception):
    """Signature, audience, issuer, or expiry check failed."""


# Backward-compat alias for external callers; preferred name follows N818.
IdTokenInvalid = IdTokenInvalidError


def verify_id_token(
    *,
    id_token: str,
    jwks: dict[str, Any],
    audience: str,
    issuer: str | None = None,
    leeway_seconds: int = 60,
    now_ts: int | None = None,
) -> dict[str, Any]:
    """Decode + verify an OIDC ID token against the provider's JWKS.

    Raises IdTokenInvalidError if signature, audience, issuer, exp, iat fail.
    Returns the claims dict on success."""
    if not jwks:
        raise IdTokenInvalidError("no_jwks_supplied")
    try:
        keyset = JsonWebKey.import_key_set(jwks)
        decoded = JsonWebToken(["RS256", "ES256"]).decode(
            id_token,
            key=keyset,
        )
    except JoseError as e:
        raise IdTokenInvalidError(f"signature_or_decode_failed:{type(e).__name__}") from e
    claims: dict[str, Any] = dict(decoded)
    now = now_ts if now_ts is not None else int(time.time())
    aud_claim = claims.get("aud")
    if isinstance(aud_claim, str):
        if aud_claim != audience:
            raise IdTokenInvalid("audience_mismatch")
    elif isinstance(aud_claim, list):
        if audience not in aud_claim:
            raise IdTokenInvalid("audience_mismatch")
    else:
        raise IdTokenInvalid("audience_claim_missing")
    if issuer is not None and claims.get("iss") != issuer:
        raise IdTokenInvalid("issuer_mismatch")
    exp = claims.get("exp")
    if not isinstance(exp, int | float) or now > int(exp) + leeway_seconds:
        raise IdTokenInvalid("token_expired")
    iat = claims.get("iat")
    if isinstance(iat, int | float) and int(iat) - leeway_seconds > now:
        raise IdTokenInvalid("token_issued_in_future")
    return claims
