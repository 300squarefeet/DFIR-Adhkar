"""Symmetric encryption helpers for at-rest secrets (TOTP seed)."""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet


def _derive_fernet_key(secret: str) -> bytes:
    """Derive a 32-byte URL-safe base64 Fernet key from ADHKAR_SECRET_KEY."""
    digest = hashlib.sha256(secret.encode()).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt(plain: bytes, secret: str) -> bytes:
    """Encrypt with Fernet (AES-128-CBC + HMAC-SHA256). Returns ciphertext bytes."""
    f = Fernet(_derive_fernet_key(secret))
    return f.encrypt(plain)


def decrypt(cipher: bytes, secret: str) -> bytes:
    """Decrypt Fernet ciphertext."""
    f = Fernet(_derive_fernet_key(secret))
    return f.decrypt(cipher)
