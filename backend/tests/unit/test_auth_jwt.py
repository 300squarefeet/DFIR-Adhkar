from datetime import timedelta
from uuid import uuid4

import jwt
import pytest
from adhkar.auth.jwt import decode_jwt, encode_jwt

SECRET = "x" * 32


def test_encode_round_trip_access():
    uid, oid = uuid4(), uuid4()
    token, claims = encode_jwt(
        secret=SECRET,
        user_id=uid,
        typ="access",
        ttl=timedelta(minutes=15),
        org_id=oid,
        perms=["viewCase", "manageUser"],
    )
    decoded = decode_jwt(token, secret=SECRET)
    assert decoded.user_id == uid
    assert decoded.org_uuid == oid
    assert set(decoded.perms) == {"viewCase", "manageUser"}
    assert decoded.typ == "access"
    assert decoded.jti == claims.jti


def test_encode_refresh_without_org():
    uid = uuid4()
    token, _ = encode_jwt(
        secret=SECRET,
        user_id=uid,
        typ="refresh",
        ttl=timedelta(days=14),
        org_id=None,
    )
    decoded = decode_jwt(token, secret=SECRET)
    assert decoded.org_id is None
    assert decoded.org_uuid is None
    assert decoded.typ == "refresh"


def test_decode_rejects_tampered_signature():
    token, _ = encode_jwt(
        secret=SECRET,
        user_id=uuid4(),
        typ="access",
        ttl=timedelta(minutes=15),
        org_id=None,
    )
    with pytest.raises(jwt.InvalidTokenError):
        decode_jwt(token, secret="different-secret-also-32-chars-x")


def test_decode_rejects_expired():
    token, _ = encode_jwt(
        secret=SECRET,
        user_id=uuid4(),
        typ="access",
        ttl=timedelta(seconds=-1),
        org_id=None,
    )
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_jwt(token, secret=SECRET)
