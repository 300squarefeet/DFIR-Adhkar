"""SAML response signature + envelope verification.

Wraps pysaml2's Saml2Client.parse_authn_request_response so the ACS
endpoint can call one function and either get typed SamlClaims back
or a typed SamlVerifyError. Replay protection is handled here via
saml_replay.mark_seen so callers don't need to remember it."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import redis.asyncio as redis_async
from saml2 import BINDING_HTTP_POST
from saml2.client import Saml2Client
from saml2.config import SPConfig
from saml2.response import StatusError

from adhkar.auth.saml import SamlProviderConfig
from adhkar.auth.saml_errors import (
    SamlConfigError,
    SamlReplayError,
    SamlSignatureError,
    SamlTimingError,
)
from adhkar.auth.saml_replay import mark_seen

CLOCK_SKEW_SECONDS = 60


@dataclass(frozen=True, slots=True)
class SamlClaims:
    name_id: str
    email: str | None
    display_name: str | None
    raw_attributes: dict[str, list[str]]
    assertion_id: str
    not_on_or_after: datetime


class SamlVerifier:
    """One per provider. Owns a configured pysaml2 client."""

    def __init__(self, cfg: SamlProviderConfig, client: Saml2Client) -> None:
        self._cfg = cfg
        self._client = client

    async def verify_and_extract(
        self,
        saml_response_b64: str,
        *,
        redis: redis_async.Redis,  # type: ignore[type-arg]
    ) -> SamlClaims:
        try:
            response = self._client.parse_authn_request_response(
                saml_response_b64,
                BINDING_HTTP_POST,
                outstanding=None,
            )
        except StatusError as e:
            raise SamlSignatureError(f"status_error:{e}") from e
        except Exception as e:  # pysaml2 raises a variety of subclasses
            raise SamlSignatureError(f"parse_failed:{type(e).__name__}") from e
        if response is None:
            raise SamlSignatureError("response_none")
        assertion = response.assertion
        if assertion is None:
            raise SamlSignatureError("assertion_missing")
        not_on_or_after = self._extract_not_on_or_after(assertion)
        now = datetime.now(tz=UTC)
        ttl = max(1, int((not_on_or_after - now).total_seconds()) + CLOCK_SKEW_SECONDS)
        if await mark_seen(redis, assertion.id, ttl_seconds=ttl) is False:
            raise SamlReplayError("assertion_id_replayed")
        raw_attrs = self._extract_attrs(assertion)
        return SamlClaims(
            name_id=str(response.name_id.text) if response.name_id else "",
            email=self._first(raw_attrs, self._cfg.wanted_attributes.get("email", "mail")),
            display_name=self._first(
                raw_attrs,
                self._cfg.wanted_attributes.get("display_name", "displayName"),
            ),
            raw_attributes=raw_attrs,
            assertion_id=str(assertion.id),
            not_on_or_after=not_on_or_after,
        )

    @staticmethod
    def _extract_not_on_or_after(assertion: object) -> datetime:
        cond = getattr(assertion, "conditions", None)
        not_on_or_after = getattr(cond, "not_on_or_after", None) if cond else None
        if not not_on_or_after:
            raise SamlTimingError("conditions_missing_not_on_or_after")
        return datetime.fromisoformat(str(not_on_or_after).replace("Z", "+00:00"))

    @staticmethod
    def _extract_attrs(assertion: object) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {}
        for statement in getattr(assertion, "attribute_statement", None) or []:
            for attr in getattr(statement, "attribute", None) or []:
                name = getattr(attr, "name", None) or getattr(attr, "friendly_name", None) or ""
                if not name:
                    continue
                values = [
                    av.text for av in (getattr(attr, "attribute_value", None) or []) if av.text
                ]
                if values:
                    out[name] = values
        return out

    @staticmethod
    def _first(attrs: dict[str, list[str]], key: str) -> str | None:
        vals = attrs.get(key) or []
        return vals[0] if vals else None


def build_verifier_from_metadata_xml(
    cfg: SamlProviderConfig,
    metadata_xml: str,
) -> SamlVerifier:
    """Build a verifier from a literal metadata XML string."""
    if not cfg.sp_entity_id or not cfg.acs_url:
        raise SamlConfigError("sp_entity_id_or_acs_url_missing")
    sp_config = SPConfig()
    sp_config.load(
        {
            "entityid": cfg.sp_entity_id,
            "service": {
                "sp": {
                    "endpoints": {"assertion_consumer_service": [(cfg.acs_url, BINDING_HTTP_POST)]},
                    "want_assertions_signed": True,
                    "want_response_signed": False,
                    "allow_unsolicited": True,
                    "authn_requests_signed": False,
                    "logout_requests_signed": False,
                }
            },
            "accepted_time_diff": CLOCK_SKEW_SECONDS,
            "metadata": {"inline": [metadata_xml]},
        }
    )
    return SamlVerifier(cfg, Saml2Client(config=sp_config))
