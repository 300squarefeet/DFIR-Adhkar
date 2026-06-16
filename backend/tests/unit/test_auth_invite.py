import time
from uuid import uuid4

import pytest
from adhkar.auth.invite import (
    InvitePayload,
    ResetPayload,
    sign_invite,
    sign_reset,
    verify_invite,
    verify_reset,
)

SECRET = "x" * 32


def test_invite_round_trip():
    p = InvitePayload(user_id=uuid4(), org_id=uuid4(), profile_id=uuid4())
    token = sign_invite(SECRET, p)
    out = verify_invite(SECRET, token)
    assert out == p


def test_invite_rejects_tampered():
    p = InvitePayload(user_id=uuid4(), org_id=uuid4(), profile_id=uuid4())
    token = sign_invite(SECRET, p)
    with pytest.raises(ValueError) as exc:
        verify_invite("different-secret-32-chars-xxxxxx", token)
    assert "invite_invalid" in str(exc.value)


def test_invite_rejects_expired():
    p = InvitePayload(user_id=uuid4(), org_id=uuid4(), profile_id=uuid4())
    token = sign_invite(SECRET, p)
    # sleep at least 2s to exceed max_age=1
    time.sleep(2)
    with pytest.raises(ValueError) as exc:
        verify_invite(SECRET, token, max_age=1)
    assert "invite_expired" in str(exc.value)


def test_reset_round_trip():
    p = ResetPayload(user_id=uuid4())
    token = sign_reset(SECRET, p)
    out = verify_reset(SECRET, token)
    assert out == p
