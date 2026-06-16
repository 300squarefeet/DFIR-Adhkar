"""Phase 10: rate limit bucket selector tests (pure-fn, no Redis)."""

from __future__ import annotations

from adhkar.core.ratelimit import _route_bucket


def test_default_bucket_for_unknown_route() -> None:
    bucket, limit = _route_bucket("/v1/cases")
    assert bucket == "default"
    assert limit == 600


def test_login_route_has_tight_bucket() -> None:
    bucket, limit = _route_bucket("/v1/auth/login")
    assert bucket == "/v1/auth/login"
    assert limit == 10


def test_mfa_prefix_routes_share_bucket() -> None:
    b1, l1 = _route_bucket("/v1/auth/mfa/enroll")
    b2, l2 = _route_bucket("/v1/auth/mfa/confirm")
    assert b1 == b2 == "/v1/auth/mfa"
    assert l1 == l2 == 20


def test_user_routes_use_user_bucket() -> None:
    bucket, limit = _route_bucket("/v1/users/abc/lock")
    assert bucket == "/v1/users"
    assert limit == 60
