import pytest
from adhkar.auth.password import (
    MIN_LENGTH,
    PasswordPolicyError,
    hash_password,
    needs_rehash,
    validate_password_policy,
    verify_password,
)


def test_hash_then_verify_round_trip():
    h = hash_password("CorrectHorseBatteryStaple-2026!")
    assert verify_password(h, "CorrectHorseBatteryStaple-2026!")
    assert not verify_password(h, "wrong")


def test_verify_returns_false_on_bad_hash():
    assert not verify_password("$argon2id$bogus", "anything")


def test_needs_rehash_false_for_current_params():
    h = hash_password("CorrectHorseBatteryStaple-2026!")
    assert needs_rehash(h) is False


def test_policy_rejects_short():
    with pytest.raises(PasswordPolicyError) as exc:
        validate_password_policy("short", hibp=False)
    assert "at least" in str(exc.value) and str(MIN_LENGTH) in str(exc.value)


def test_policy_rejects_weak_zxcvbn():
    with pytest.raises(PasswordPolicyError) as exc:
        validate_password_policy("password1234", hibp=False)
    assert "zxcvbn" in str(exc.value).lower() or "weak" in str(exc.value).lower()


def test_policy_accepts_strong():
    validate_password_policy("Correct-Horse-Battery-Staple-2026!", hibp=False)


def test_hibp_softfail_does_not_block_offline(monkeypatch):
    # When HIBP API is unreachable (we don't go to network in tests by default),
    # the call still returns OK because soft-fail is the contract.
    import adhkar.auth.password as pw

    def boom(*_a, **_k):
        raise RuntimeError("network down")

    monkeypatch.setattr(pw.httpx, "get", boom)
    # strong password + HIBP unreachable => no exception
    validate_password_policy("Correct-Horse-Battery-Staple-2026!", hibp=True)
