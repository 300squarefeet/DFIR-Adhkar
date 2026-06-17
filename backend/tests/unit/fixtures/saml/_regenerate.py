# ruff: noqa: E501
"""Regenerate the committed SAML test fixtures.

Run this once from `backend/`:
    uv run python tests/unit/fixtures/saml/_regenerate.py

It builds two self-signed cert/key pairs (valid IdP + attacker), an
IdP metadata document that lists the valid IdP cert, and seven
SAMLResponse XML documents (signed or unsigned) covering each
verifier rejection branch.

Idempotent: produces byte-identical output for a given input. Commit
the resulting .pem and .xml files alongside this script. Do NOT run
in CI.
"""

from __future__ import annotations

import pathlib
import subprocess
import tempfile
from datetime import UTC, datetime, timedelta

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

FIXTURES_DIR = pathlib.Path(__file__).parent

OUR_ACS_URL = "https://adhkar.test/v1/auth/saml/test/acs"
OUR_SP_ENTITY_ID = "https://adhkar.test/api/v1/auth/saml/test/metadata"
IDP_ENTITY_ID = "https://idp.test/saml/metadata"
IDP_SSO_URL = "https://idp.test/saml/sso"

NOW = datetime(2026, 6, 17, 12, 0, 0, tzinfo=UTC)
WINDOW = timedelta(minutes=5)


def _generate_keypair(common_name: str) -> tuple[bytes, bytes]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(NOW - timedelta(days=365))
        .not_valid_after(NOW + timedelta(days=3650))
        .sign(key, hashes.SHA256())
    )
    key_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )
    cert_pem = cert.public_bytes(encoding=serialization.Encoding.PEM)
    return cert_pem, key_pem


def _signature_template(assertion_id: str) -> str:
    """An enveloped XML-DSig template for xmlsec1 to fill in.

    The Reference URI points at the Assertion's ID. xmlsec1 will
    compute the digest, canonicalize the assertion, and emit the
    SignatureValue. The KeyInfo carries an EMPTY <X509Certificate/>
    placeholder; xmlsec1 fills it in from the cert passed via
    `--privkey-pem key,cert` so pysaml2's verify path (which runs
    xmlsec1 with --enabled-key-data raw-x509-cert) can locate the
    signing key from the document itself.
    """
    return f"""<ds:Signature xmlns:ds="http://www.w3.org/2000/09/xmldsig#">
      <ds:SignedInfo>
        <ds:CanonicalizationMethod Algorithm="http://www.w3.org/2001/10/xml-exc-c14n#"/>
        <ds:SignatureMethod Algorithm="http://www.w3.org/2001/04/xmldsig-more#rsa-sha256"/>
        <ds:Reference URI="#{assertion_id}">
          <ds:Transforms>
            <ds:Transform Algorithm="http://www.w3.org/2000/09/xmldsig#enveloped-signature"/>
            <ds:Transform Algorithm="http://www.w3.org/2001/10/xml-exc-c14n#"/>
          </ds:Transforms>
          <ds:DigestMethod Algorithm="http://www.w3.org/2001/04/xmlenc#sha256"/>
          <ds:DigestValue></ds:DigestValue>
        </ds:Reference>
      </ds:SignedInfo>
      <ds:SignatureValue></ds:SignatureValue>
      <ds:KeyInfo>
        <ds:X509Data>
          <ds:X509Certificate></ds:X509Certificate>
        </ds:X509Data>
      </ds:KeyInfo>
    </ds:Signature>"""


def _sign_with_xmlsec1(
    template_xml: str,
    key_pem_path: pathlib.Path,
    cert_pem_path: pathlib.Path,
    assertion_id: str,
) -> str:
    """Sign the <saml:Assertion> by shelling out to xmlsec1 directly.

    The template carries a <ds:Signature> with a populated KeyInfo/X509
    block, so xmlsec1 needs the matching key + cert pair to compute the
    SignatureValue. pysaml2's own sign_statement only accepts a private
    key (no cert), which fails when the template already embeds a cert,
    so we invoke xmlsec1 ourselves with the `key,cert` form of
    --privkey-pem. The resulting XML is byte-compatible with pysaml2's
    verify path (CryptoBackendXmlSec1.validate_signature uses the same
    xmlsec1 binary with --enabled-key-data raw-x509-cert).
    """
    with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as src:
        src.write(template_xml)
        src_path = src.name
    out_path = src_path + ".signed"
    try:
        cmd = [
            "xmlsec1",
            "--sign",
            "--lax-key-search",
            "--privkey-pem",
            f"{key_pem_path},{cert_pem_path}",
            "--id-attr:ID",
            "urn:oasis:names:tc:SAML:2.0:assertion:Assertion",
            "--node-id",
            assertion_id,
            "--output",
            out_path,
            src_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise RuntimeError(
                f"xmlsec1 --sign failed (rc={result.returncode})\n"
                f"stdout: {result.stdout}\nstderr: {result.stderr}"
            )
        return pathlib.Path(out_path).read_text()
    finally:
        pathlib.Path(src_path).unlink(missing_ok=True)
        pathlib.Path(out_path).unlink(missing_ok=True)


def _build_response_xml(
    *,
    assertion_id: str,
    not_before: datetime,
    not_on_or_after: datetime,
    audience: str,
    recipient: str,
    name_id: str = "soc@example.test",
    with_signature_template: bool = True,
) -> str:
    signature_block = _signature_template(assertion_id) if with_signature_template else ""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<samlp:Response xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol"
                xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion"
                ID="response-{assertion_id}"
                IssueInstant="{NOW.isoformat()}"
                Version="2.0"
                Destination="{recipient}">
  <saml:Issuer>{IDP_ENTITY_ID}</saml:Issuer>
  <samlp:Status>
    <samlp:StatusCode Value="urn:oasis:names:tc:SAML:2.0:status:Success"/>
  </samlp:Status>
  <saml:Assertion xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion" ID="{assertion_id}" IssueInstant="{NOW.isoformat()}" Version="2.0">
    <saml:Issuer>{IDP_ENTITY_ID}</saml:Issuer>
    {signature_block}
    <saml:Subject>
      <saml:NameID Format="urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress">{name_id}</saml:NameID>
      <saml:SubjectConfirmation Method="urn:oasis:names:tc:SAML:2.0:cm:bearer">
        <saml:SubjectConfirmationData Recipient="{recipient}" NotOnOrAfter="{not_on_or_after.isoformat()}"/>
      </saml:SubjectConfirmation>
    </saml:Subject>
    <saml:Conditions NotBefore="{not_before.isoformat()}" NotOnOrAfter="{not_on_or_after.isoformat()}">
      <saml:AudienceRestriction>
        <saml:Audience>{audience}</saml:Audience>
      </saml:AudienceRestriction>
    </saml:Conditions>
    <saml:AttributeStatement>
      <saml:Attribute Name="mail">
        <saml:AttributeValue>{name_id}</saml:AttributeValue>
      </saml:Attribute>
      <saml:Attribute Name="displayName">
        <saml:AttributeValue>SOC Bot</saml:AttributeValue>
      </saml:Attribute>
    </saml:AttributeStatement>
  </saml:Assertion>
</samlp:Response>
"""


def _idp_metadata_xml(cert_pem: bytes) -> str:
    # PEM body between BEGIN/END markers IS already the base64 of the DER cert.
    # SAML metadata expects exactly that single-base64 string in <ds:X509Certificate>.
    b64_cert = (
        cert_pem.replace(b"-----BEGIN CERTIFICATE-----", b"")
        .replace(b"-----END CERTIFICATE-----", b"")
        .replace(b"\n", b"")
        .decode()
    )
    return f"""<?xml version="1.0"?>
<md:EntityDescriptor xmlns:md="urn:oasis:names:tc:SAML:2.0:metadata"
                     xmlns:ds="http://www.w3.org/2000/09/xmldsig#"
                     entityID="{IDP_ENTITY_ID}">
  <md:IDPSSODescriptor protocolSupportEnumeration="urn:oasis:names:tc:SAML:2.0:protocol">
    <md:KeyDescriptor use="signing">
      <ds:KeyInfo>
        <ds:X509Data>
          <ds:X509Certificate>{b64_cert}</ds:X509Certificate>
        </ds:X509Data>
      </ds:KeyInfo>
    </md:KeyDescriptor>
    <md:SingleSignOnService Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"
                            Location="{IDP_SSO_URL}"/>
  </md:IDPSSODescriptor>
</md:EntityDescriptor>
"""


def main() -> None:
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Keypairs
    valid_cert_pem, valid_key_pem = _generate_keypair("test-idp")
    (FIXTURES_DIR / "valid_idp_cert.pem").write_bytes(valid_cert_pem)
    (FIXTURES_DIR / "valid_idp_key.pem").write_bytes(valid_key_pem)

    attacker_cert_pem, attacker_key_pem = _generate_keypair("attacker-idp")
    (FIXTURES_DIR / "attacker_cert.pem").write_bytes(attacker_cert_pem)
    (FIXTURES_DIR / "attacker_key.pem").write_bytes(attacker_key_pem)

    # 2. IdP metadata
    (FIXTURES_DIR / "valid_idp_metadata.xml").write_text(_idp_metadata_xml(valid_cert_pem))

    cases = [
        (
            "valid_response.xml",
            {
                "assertion_id": "assertion-valid",
                "not_before": NOW - WINDOW,
                "not_on_or_after": NOW + WINDOW,
                "audience": OUR_SP_ENTITY_ID,
                "recipient": OUR_ACS_URL,
            },
            "valid",
        ),
        (
            "wrong_signer_response.xml",
            {
                "assertion_id": "assertion-wrongsigner",
                "not_before": NOW - WINDOW,
                "not_on_or_after": NOW + WINDOW,
                "audience": OUR_SP_ENTITY_ID,
                "recipient": OUR_ACS_URL,
            },
            "attacker",
        ),
        (
            "expired_response.xml",
            {
                "assertion_id": "assertion-expired",
                "not_before": datetime(1970, 1, 1, tzinfo=UTC),
                "not_on_or_after": datetime(1970, 1, 2, tzinfo=UTC),
                "audience": OUR_SP_ENTITY_ID,
                "recipient": OUR_ACS_URL,
            },
            "valid",
        ),
        (
            "not_yet_valid_response.xml",
            {
                "assertion_id": "assertion-nyv",
                "not_before": datetime(9999, 1, 1, tzinfo=UTC),
                "not_on_or_after": datetime(9999, 1, 2, tzinfo=UTC),
                "audience": OUR_SP_ENTITY_ID,
                "recipient": OUR_ACS_URL,
            },
            "valid",
        ),
        (
            "wrong_audience_response.xml",
            {
                "assertion_id": "assertion-wrongaudience",
                "not_before": NOW - WINDOW,
                "not_on_or_after": NOW + WINDOW,
                "audience": "https://someone-else.invalid/",
                "recipient": OUR_ACS_URL,
            },
            "valid",
        ),
        (
            "wrong_recipient_response.xml",
            {
                "assertion_id": "assertion-wrongrecipient",
                "not_before": NOW - WINDOW,
                "not_on_or_after": NOW + WINDOW,
                "audience": OUR_SP_ENTITY_ID,
                "recipient": "https://attacker.test/acs",
            },
            "valid",
        ),
    ]
    for filename, kwargs, signer in cases:
        signer_key_path = FIXTURES_DIR / (
            "valid_idp_key.pem" if signer == "valid" else "attacker_key.pem"
        )
        signer_cert_path = FIXTURES_DIR / (
            "valid_idp_cert.pem" if signer == "valid" else "attacker_cert.pem"
        )
        unsigned_template = _build_response_xml(with_signature_template=True, **kwargs)
        (FIXTURES_DIR / filename).write_text(
            _sign_with_xmlsec1(
                unsigned_template, signer_key_path, signer_cert_path, kwargs["assertion_id"]
            )
        )

    # Unsigned response: no Signature element at all
    (FIXTURES_DIR / "unsigned_response.xml").write_text(
        _build_response_xml(
            assertion_id="assertion-unsigned",
            not_before=NOW - WINDOW,
            not_on_or_after=NOW + WINDOW,
            audience=OUR_SP_ENTITY_ID,
            recipient=OUR_ACS_URL,
            with_signature_template=False,
        )
    )

    print(f"Wrote {len(list(FIXTURES_DIR.glob('*')))} files to {FIXTURES_DIR}")


if __name__ == "__main__":
    main()
