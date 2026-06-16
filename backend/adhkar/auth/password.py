"""Password hashing (argon2id), validation policy, optional HIBP breach check."""

from __future__ import annotations

import hashlib
import logging

import httpx
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from zxcvbn import zxcvbn

_log = logging.getLogger(__name__)

# Argon2id parameters per ADR 0006 §"Password hashing parameters".
# Note: lower-cost in tests via override_hasher() if needed.
_hasher = PasswordHasher(
    time_cost=2,
    memory_cost=64 * 1024,  # 64 MiB
    parallelism=2,
    hash_len=32,
)

MIN_LENGTH = 12
MIN_ZXCVBN_SCORE = 3  # 0-4 scale; 3 = "safely unguessable: moderate protection"

# HIBP "have I been pwned" API root (k-anonymity range query).
HIBP_BASE_URL = "https://api.pwnedpasswords.com/range/"


class PasswordPolicyError(ValueError):
    """Raised when a password fails policy."""


def hash_password(plain: str) -> str:
    """Hash a plain password to argon2id."""
    return _hasher.hash(plain)


def verify_password(stored_hash: str, plain: str) -> bool:
    """Constant-time verification. Returns True/False; never raises on mismatch."""
    try:
        return _hasher.verify(stored_hash, plain)
    except VerifyMismatchError:
        return False
    except Exception:
        _log.exception("argon2 verify error")
        return False


def needs_rehash(stored_hash: str) -> bool:
    """Whether stored hash uses outdated argon2 params and should be rehashed on next login."""
    return _hasher.check_needs_rehash(stored_hash)


def validate_password_policy(plain: str, *, hibp: bool = True) -> None:
    """Enforce length, strength, optional breach check. Raises PasswordPolicyError on fail.

    `hibp=True` triggers the HaveIBeenPwned k-anonymity API; on network error
    we soft-fail (log warning, accept the password). HIBP is a bonus, not a gate.
    """
    if len(plain) < MIN_LENGTH:
        raise PasswordPolicyError(f"password must be at least {MIN_LENGTH} characters")

    result = zxcvbn(plain)
    if result["score"] < MIN_ZXCVBN_SCORE:
        feedback = result["feedback"]
        msg = feedback.get("warning") or "password is too weak"
        raise PasswordPolicyError(f"{msg} (zxcvbn score {result['score']}/4)")

    if hibp:
        try:
            count = _hibp_pwned_count(plain)
            if count > 0:
                raise PasswordPolicyError(
                    f"password has appeared in {count:,} known breaches; please choose another"
                )
        except PasswordPolicyError:
            raise
        except Exception as e:
            _log.warning("hibp check soft-failed: %s", e)


def _hibp_pwned_count(plain: str) -> int:
    """Query HaveIBeenPwned k-anonymity range API. Returns count of breaches (0 = safe)."""
    sha1 = hashlib.sha1(plain.encode()).hexdigest().upper()  # noqa: S324 — HIBP requires SHA-1
    prefix, suffix = sha1[:5], sha1[5:]
    resp = httpx.get(
        f"{HIBP_BASE_URL}{prefix}",
        headers={"Add-Padding": "true", "User-Agent": "adhkar-ir/0.2"},
        timeout=3.0,
    )
    resp.raise_for_status()
    for line in resp.text.splitlines():
        h, _, cnt = line.partition(":")
        if h.strip() == suffix:
            return int(cnt.strip())
    return 0
