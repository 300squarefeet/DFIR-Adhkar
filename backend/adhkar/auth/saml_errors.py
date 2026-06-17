"""Typed exceptions raised by adhkar.auth.saml_verifier.

The ACS endpoint catches each subclass and maps it to a specific HTTP
status + machine-readable error code + audit event. Each carries a
single `reason` string so the audit row diff is greppable."""

from __future__ import annotations


class SamlVerifyError(Exception):
    """Base for every SAML verification rejection."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class SamlSignatureError(SamlVerifyError):
    """XML-DSig signature absent, malformed, or signed by the wrong key."""


class SamlTimingError(SamlVerifyError):
    """NotBefore is in the future or NotOnOrAfter is in the past."""


class SamlAudienceError(SamlVerifyError):
    """AudienceRestriction does not include our SP entity_id."""


class SamlRecipientError(SamlVerifyError):
    """SubjectConfirmation.Recipient does not match our ACS URL."""


class SamlReplayError(SamlVerifyError):
    """Assertion ID was already accepted inside its validity window."""


class SamlConfigError(SamlVerifyError):
    """Internal mis-config (e.g. missing metadata at verify time)."""
