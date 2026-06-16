import pyotp
from adhkar.auth.mfa import (
    generate_backup_codes,
    generate_seed,
    provisioning_uri,
    qr_png_data_url,
    verify_backup_code,
    verify_totp,
)


def test_generate_seed_is_base32_32_chars():
    s = generate_seed()
    assert len(s) == 32
    assert s.isalnum()


def test_provisioning_uri_contains_issuer_and_account():
    s = generate_seed()
    uri = provisioning_uri(s, account_email="alice@example.com", issuer="Adhkar")
    assert uri.startswith("otpauth://totp/")
    assert "Adhkar" in uri
    assert "alice%40example.com" in uri or "alice@example.com" in uri


def test_qr_data_url_is_png_base64():
    s = generate_seed()
    data = qr_png_data_url(s, account_email="x@y.com")
    assert data.startswith("data:image/png;base64,")


def test_verify_totp_accepts_current_code():
    s = generate_seed()
    code = pyotp.TOTP(s).now()
    assert verify_totp(s, code)


def test_verify_totp_rejects_wrong_code():
    s = generate_seed()
    assert not verify_totp(s, "000000")


def test_backup_codes_round_trip():
    plain, hashed = generate_backup_codes()
    assert len(plain) == 10
    assert len(hashed) == 10
    # Each plain code matches its hash exactly once
    idx = verify_backup_code(hashed, [], plain[3])
    assert idx == 3
    # Cannot re-use the same code if its index is in used_indices
    assert verify_backup_code(hashed, [3], plain[3]) is None
    # Different code matches different index
    idx2 = verify_backup_code(hashed, [3], plain[7])
    assert idx2 == 7


def test_backup_codes_reject_unknown():
    _plain, hashed = generate_backup_codes()
    assert verify_backup_code(hashed, [], "not-a-real-code") is None
