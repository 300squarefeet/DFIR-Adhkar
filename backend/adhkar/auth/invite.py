"""Invitation token (signed link via itsdangerous)."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

INVITE_MAX_AGE_SECONDS = 24 * 60 * 60  # 24 hours
RESET_MAX_AGE_SECONDS = 60 * 60  # 1 hour

_INVITE_SALT = "adhkar.invite"
_RESET_SALT = "adhkar.password-reset"


@dataclass(frozen=True, slots=True)
class InvitePayload:
    user_id: UUID
    org_id: UUID
    profile_id: UUID


@dataclass(frozen=True, slots=True)
class ResetPayload:
    user_id: UUID


def sign_invite(secret: str, payload: InvitePayload) -> str:
    s = URLSafeTimedSerializer(secret, salt=_INVITE_SALT)
    return s.dumps(
        {
            "uid": str(payload.user_id),
            "oid": str(payload.org_id),
            "pid": str(payload.profile_id),
        }
    )


def verify_invite(
    secret: str, token: str, *, max_age: int = INVITE_MAX_AGE_SECONDS
) -> InvitePayload:
    s = URLSafeTimedSerializer(secret, salt=_INVITE_SALT)
    try:
        data = s.loads(token, max_age=max_age)
    except SignatureExpired as e:
        raise ValueError("invite_expired") from e
    except BadSignature as e:
        raise ValueError("invite_invalid") from e
    return InvitePayload(
        user_id=UUID(data["uid"]),
        org_id=UUID(data["oid"]),
        profile_id=UUID(data["pid"]),
    )


def sign_reset(secret: str, payload: ResetPayload) -> str:
    s = URLSafeTimedSerializer(secret, salt=_RESET_SALT)
    return s.dumps({"uid": str(payload.user_id)})


def verify_reset(secret: str, token: str, *, max_age: int = RESET_MAX_AGE_SECONDS) -> ResetPayload:
    s = URLSafeTimedSerializer(secret, salt=_RESET_SALT)
    try:
        data = s.loads(token, max_age=max_age)
    except SignatureExpired as e:
        raise ValueError("reset_expired") from e
    except BadSignature as e:
        raise ValueError("reset_invalid") from e
    return ResetPayload(user_id=UUID(data["uid"]))
