"""SAML 2.0 SP-initiated SSO foundation.

Same shape as the OIDC module: declarative config + state-as-HMAC, no
session store. We deliberately keep this thin — full SAML XML signing/
encryption uses python-saml/python3-saml in a follow-up. This module
ships the configuration + assertion-claim extraction primitives that
already need exhaustive tests:

- SAML provider config loader (env-driven, mirrors OIDC).
- minimal Assertion attribute extractor that pulls email/name from a
  signed SAML <saml:Assertion> XML payload (signature verification is
  intentionally NOT here — pysaml2 handles that in the live IdP path).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from xml.etree import ElementTree as ET

from defusedxml import ElementTree as DefusedET  # type: ignore[import-untyped]

from adhkar.core.settings import Settings


@dataclass(frozen=True, slots=True)
class SamlProviderConfig:
    name: str
    idp_entity_id: str
    idp_sso_url: str
    sp_entity_id: str
    acs_url: str
    idp_certificate_pem: str = ""


_SAML_NS = {
    "saml": "urn:oasis:names:tc:SAML:2.0:assertion",
}


def load_saml_providers(settings: Settings) -> dict[str, SamlProviderConfig]:
    """Parse `settings.saml_providers_json`. Same shape as load_providers
    in adhkar.auth.oidc."""
    raw = settings.saml_providers_json or ""
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(parsed, dict):
        return {}
    out: dict[str, SamlProviderConfig] = {}
    for name, cfg in parsed.items():
        if not isinstance(cfg, dict):
            continue
        try:
            out[str(name)] = SamlProviderConfig(
                name=str(name),
                idp_entity_id=str(cfg["idp_entity_id"]),
                idp_sso_url=str(cfg["idp_sso_url"]),
                sp_entity_id=str(cfg["sp_entity_id"]),
                acs_url=str(cfg["acs_url"]),
                idp_certificate_pem=str(cfg.get("idp_certificate_pem", "")),
            )
        except (KeyError, TypeError):
            continue
    return out


def extract_assertion_attributes(saml_xml: str) -> dict[str, str]:
    """Parse the AttributeStatement out of a SAML Assertion XML and return
    {AttributeName: first-value}.

    Parsing goes through defusedxml so we are not vulnerable to XXE or
    billion-laughs entity-expansion attacks against IdP-supplied XML.
    Signature verification still lives in the full SAML library
    (pysaml2) in the live IdP path; this helper only extracts claims
    AFTER the document has been verified by that library."""
    try:
        root = DefusedET.fromstring(saml_xml)
    except ET.ParseError:
        return {}
    attrs: dict[str, str] = {}
    for attr in root.iter(f"{{{_SAML_NS['saml']}}}Attribute"):
        name = attr.get("Name") or attr.get("FriendlyName") or ""
        if not name:
            continue
        value_elem = attr.find(f"{{{_SAML_NS['saml']}}}AttributeValue")
        if value_elem is not None and value_elem.text:
            attrs[name] = value_elem.text.strip()
    # Try NameID as a default email fallback.
    name_id = root.find(f".//{{{_SAML_NS['saml']}}}NameID")
    if name_id is not None and name_id.text and "email" not in attrs:
        attrs["NameID"] = name_id.text.strip()
    return attrs
