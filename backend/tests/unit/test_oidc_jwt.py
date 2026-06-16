"""OIDC ID-token verification tests using a locally-minted RSA keypair."""

from __future__ import annotations

import time

import pytest
from adhkar.auth.oidc_jwt import IdTokenInvalid, verify_id_token
from joserfc import jwt  # type: ignore[import-untyped]
from joserfc.jwk import RSAKey  # type: ignore[import-untyped]


def _make_keypair_and_jwks() -> tuple[RSAKey, dict]:
    """Generate a fresh RSA keypair the test JWT will be signed with, plus
    the JWKS the verifier consumes."""
    key = RSAKey.generate_key(2048, parameters={"kid": "test-kid"})
    pub = key.as_dict(private=False)
    pub["alg"] = "RS256"
    pub["use"] = "sig"
    pub["kid"] = "test-kid"
    jwks = {"keys": [pub]}
    return key, jwks


def _mint_token(key: RSAKey, claims: dict) -> str:
    return jwt.encode({"alg": "RS256", "kid": "test-kid"}, claims, key)


def test_verifies_well_formed_token() -> None:
    key, jwks = _make_keypair_and_jwks()
    now = int(time.time())
    token = _mint_token(
        key,
        {
            "iss": "https://idp.test",
            "aud": "adhkar-client",
            "sub": "soc@example.test",
            "email": "soc@example.test",
            "iat": now,
            "exp": now + 600,
        },
    )
    claims = verify_id_token(
        id_token=token, jwks=jwks, audience="adhkar-client", issuer="https://idp.test"
    )
    assert claims["email"] == "soc@example.test"


def test_rejects_audience_mismatch() -> None:
    key, jwks = _make_keypair_and_jwks()
    now = int(time.time())
    token = _mint_token(key, {"iss": "i", "aud": "wrong", "iat": now, "exp": now + 600})
    with pytest.raises(IdTokenInvalid, match="audience_mismatch"):
        verify_id_token(id_token=token, jwks=jwks, audience="adhkar-client")


def test_rejects_expired_token() -> None:
    key, jwks = _make_keypair_and_jwks()
    now = int(time.time())
    token = _mint_token(
        key,
        {"iss": "i", "aud": "adhkar-client", "iat": now - 7200, "exp": now - 3600},
    )
    with pytest.raises(IdTokenInvalid, match="token_expired"):
        verify_id_token(id_token=token, jwks=jwks, audience="adhkar-client")


def test_rejects_issuer_mismatch() -> None:
    key, jwks = _make_keypair_and_jwks()
    now = int(time.time())
    token = _mint_token(
        key,
        {
            "iss": "https://impostor.test",
            "aud": "adhkar-client",
            "iat": now,
            "exp": now + 600,
        },
    )
    with pytest.raises(IdTokenInvalid, match="issuer_mismatch"):
        verify_id_token(
            id_token=token,
            jwks=jwks,
            audience="adhkar-client",
            issuer="https://idp.test",
        )


def test_rejects_signature_when_jwks_does_not_match() -> None:
    key_a, _ = _make_keypair_and_jwks()
    _, jwks_b = _make_keypair_and_jwks()
    now = int(time.time())
    token = _mint_token(
        key_a,
        {"iss": "i", "aud": "adhkar-client", "iat": now, "exp": now + 600},
    )
    with pytest.raises(IdTokenInvalid, match="signature_or_decode_failed"):
        verify_id_token(id_token=token, jwks=jwks_b, audience="adhkar-client")


def test_rejects_when_jwks_empty() -> None:
    with pytest.raises(IdTokenInvalid, match="no_jwks_supplied"):
        verify_id_token(id_token="any.jwt.thing", jwks={}, audience="x")
