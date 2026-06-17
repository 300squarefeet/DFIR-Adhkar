"""Type-level tests for the SAML error hierarchy."""

from __future__ import annotations

import pytest
from adhkar.auth.saml_errors import (
    SamlAudienceError,
    SamlConfigError,
    SamlRecipientError,
    SamlReplayError,
    SamlSignatureError,
    SamlTimingError,
    SamlVerifyError,
)


@pytest.mark.parametrize(
    "subclass",
    [
        SamlSignatureError,
        SamlTimingError,
        SamlAudienceError,
        SamlRecipientError,
        SamlReplayError,
        SamlConfigError,
    ],
)
def test_all_subclass_samlverifyerror(subclass: type[Exception]) -> None:
    assert issubclass(subclass, SamlVerifyError)


def test_error_carries_reason() -> None:
    exc = SamlSignatureError("digest_mismatch")
    assert str(exc) == "digest_mismatch"
    assert exc.reason == "digest_mismatch"
