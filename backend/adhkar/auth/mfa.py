"""TOTP MFA + backup codes."""

from __future__ import annotations

import base64
import io
import secrets
from urllib.parse import quote

import pyotp
import qrcode
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

_TOTP_DIGITS = 6
_TOTP_PERIOD = 30
_BACKUP_CODE_COUNT = 10
_BACKUP_CODE_BYTES = 6  # 12 hex chars

_hasher = PasswordHasher()


def generate_seed() -> str:
    """Generate a fresh base32 TOTP secret (160 bits = 32 base32 chars)."""
    return pyotp.random_base32()


def provisioning_uri(secret: str, *, account_email: str, issuer: str = "Adhkar") -> str:
    """Build `otpauth://` URI for QR enrollment."""
    return pyotp.TOTP(secret).provisioning_uri(name=account_email, issuer_name=issuer)


def qr_png_data_url(secret: str, *, account_email: str, issuer: str = "Adhkar") -> str:
    """Return a `data:image/png;base64,...` URL for direct <img src=> embedding."""
    uri = provisioning_uri(secret, account_email=account_email, issuer=issuer)
    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode()}"


def verify_totp(secret: str, code: str) -> bool:
    """Verify a 6-digit code with ±1 window (90 s acceptance band)."""
    return pyotp.TOTP(secret, digits=_TOTP_DIGITS, interval=_TOTP_PERIOD).verify(
        code, valid_window=1
    )


def generate_backup_codes() -> tuple[list[str], list[str]]:
    """Return (plain_codes, hashed_codes). Plain are shown ONCE to user."""
    plain = [secrets.token_hex(_BACKUP_CODE_BYTES) for _ in range(_BACKUP_CODE_COUNT)]
    hashed = [_hasher.hash(c) for c in plain]
    return plain, hashed


def verify_backup_code(stored_hashes: list[str], used_indices: list[int], code: str) -> int | None:
    """Return the matching index if a hash matches AND not previously used; else None.

    Caller should atomically append the returned index to backup_codes_used.
    """
    for i, h in enumerate(stored_hashes):
        if i in used_indices:
            continue
        try:
            _hasher.verify(h, code)
            return i
        except VerifyMismatchError:
            continue
    return None


def encode_uri(s: str) -> str:
    """URL-encode helper (re-exported for tests)."""
    return quote(s, safe="")
