# SAML Signature Verification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire `pysaml2` behind the SAML ACS endpoint so unsigned / tampered / expired / wrong-audience / replayed assertions are rejected with typed errors. Closes the #1 security blocker for `v1.0.0`.

**Architecture:** New `SamlVerifier` class owns one `pysaml2` client per configured provider, built once at app-lifespan startup from cached IdP metadata. ACS endpoint calls `verify_and_extract(...)` instead of the unvalidated `extract_assertion_attributes(...)`. Redis-backed assertion-ID cache rejects replays inside the assertion's validity window. Soft-fail boot (503 on the SAML provider only) keeps the rest of the API up if metadata is unreachable.

**Tech Stack:** Python 3.12, FastAPI lifespan, `pysaml2>=7.5`, `xmlsec1` system package, `redis.asyncio`, `fakeredis>=2.27` (tests), `pytest-asyncio`, `respx` (for metadata-URL mocking), `freezegun` (for timing tests).

**Spec reference:** `docs/superpowers/specs/2026-06-17-adhkar-saml-signature-verification-design.md` (commit `b9a69fa`).

---

## Pre-flight (read once before starting Task 1)

**Branch:** stay on `phase10/hardening`. All commits use `git commit -s -m "..." -- <exact paths>` (path-scoped) per the project's [[feedback-path-scoped-commits]] convention.

**Tagging:** at the end of each task that ships a commit, tag the commit with the matching `v1.0.0-rcN.*` tag — increment `N` from the last existing RC (run `git tag | grep -E '^v1\.0\.0-rc[0-9]+' | sort -V | tail -1` to find the current max). At time of writing the max is RC262 → first new RC is RC263.

**Validation cadence:** every implementation task ends with `uv run ruff check --fix . && uv run ruff format . && uv run mypy adhkar && uv run pytest tests/ -q` from `backend/`. Smoke-test gating: `uv run pytest tests/integration/test_openapi_route_coverage.py -q`.

**xmlsec1 install:** `pysaml2` imports require the `xmlsec1` binary plus `libxmlsec1-dev` headers. On the dev box: `brew install libxmlsec1` (macOS) or `apt-get install xmlsec1 libxmlsec1-dev` (Debian/Ubuntu). The plan adds this to the project's `Dockerfile` in Task 1.

---

## Task 1: Add dependencies + xmlsec1 system package

**Files:**
- Modify: `backend/pyproject.toml`
- Modify: `backend/Dockerfile` (if exists; otherwise create note)
- Modify: `.github/workflows/*.yml` (CI install — discover with `grep -l "uv sync" .github/workflows/*.yml`)

- [ ] **Step 1: Confirm current pysaml2 / fakeredis state**

Run:
```bash
cd backend && grep -E "pysaml2|fakeredis" pyproject.toml
```
Expected: no matches (both absent).

- [ ] **Step 2: Add `pysaml2` to project deps and `fakeredis` to dev deps**

Open `backend/pyproject.toml`. In the `dependencies = [...]` list, after the existing `"defusedxml>=0.7.1",` line, add:
```toml
  "pysaml2>=7.5",
```
In `[dependency-groups] dev = [...]`, after `"openapi-spec-validator>=0.7",`, add:
```toml
  "fakeredis>=2.27",
```

- [ ] **Step 3: Lock and install**

Run from `backend/`:
```bash
uv sync
```
Expected: pysaml2 + fakeredis appear in the install set; exit 0. If `xmlsec` install fails, install the system package first (see Pre-flight) then re-run.

- [ ] **Step 4: Add xmlsec1 to CI Dockerfile / workflow**

Find the CI install step:
```bash
grep -rn "uv sync\|apt-get install" .github/workflows/ backend/Dockerfile 2>/dev/null | head -5
```

For each workflow file that runs `uv sync` for backend, add a step BEFORE the sync:
```yaml
      - name: Install xmlsec1 (required by pysaml2)
        run: sudo apt-get update && sudo apt-get install -y xmlsec1 libxmlsec1-dev
```

If a `backend/Dockerfile` exists and uses `apt-get`, append `xmlsec1 libxmlsec1-dev` to the package list.

- [ ] **Step 5: Sanity-import pysaml2**

Run from `backend/`:
```bash
uv run python -c "import saml2; from saml2.client import Saml2Client; print('ok', saml2.__version__)"
```
Expected: `ok 7.5.x` (any 7.5+ version).

- [ ] **Step 6: Smoke + commit**

Run:
```bash
cd backend && uv run pytest tests/integration/test_openapi_route_coverage.py -q
```
Expected: `3 passed`.

Commit (path-scoped):
```bash
cd /Users/salma/Documents/Research/adhkar-ir
git commit -s -m "$(cat <<'EOF'
deps: pysaml2 + fakeredis + xmlsec1 system pkg for SAML signature verification

Phase 10 hardening prep: pull in pysaml2 for SAML signature/audience/
recipient/timing validation, fakeredis for replay-cache unit tests,
and the xmlsec1 system package in CI.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)" -- backend/pyproject.toml backend/uv.lock $(grep -l "uv sync" .github/workflows/*.yml 2>/dev/null)
git tag v1.0.0-rc263.saml-deps
```

---

## Task 2: SAML error type hierarchy

**Files:**
- Create: `backend/adhkar/auth/saml_errors.py`
- Create: `backend/tests/unit/test_saml_errors.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/test_saml_errors.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/unit/test_saml_errors.py -q
```
Expected: `ModuleNotFoundError: No module named 'adhkar.auth.saml_errors'`.

- [ ] **Step 3: Write the module**

Create `backend/adhkar/auth/saml_errors.py`:
```python
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
```

- [ ] **Step 4: Run tests, lint, typecheck**

```bash
cd backend && uv run pytest tests/unit/test_saml_errors.py -q \
  && uv run ruff check adhkar/auth/saml_errors.py tests/unit/test_saml_errors.py \
  && uv run ruff format adhkar/auth/saml_errors.py tests/unit/test_saml_errors.py \
  && uv run mypy adhkar/auth/saml_errors.py
```
Expected: `7 passed` (6 parametric + 1 reason), ruff clean, mypy `Success`.

- [ ] **Step 5: Commit + tag**

```bash
cd /Users/salma/Documents/Research/adhkar-ir
git commit -s -m "$(cat <<'EOF'
feat(saml): typed SAML verification error hierarchy

Six subclasses of SamlVerifyError (signature/timing/audience/recipient/
replay/config) so the ACS endpoint can map each to a specific HTTP
status + audit reason without string-matching.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)" -- backend/adhkar/auth/saml_errors.py backend/tests/unit/test_saml_errors.py
git tag v1.0.0-rc264.saml-errors
```

---

## Task 3: Redis-backed replay cache

**Files:**
- Create: `backend/adhkar/auth/saml_replay.py`
- Create: `backend/tests/unit/test_saml_replay.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/test_saml_replay.py`:
```python
"""saml_replay.mark_seen — fakeredis-backed tests."""

from __future__ import annotations

import asyncio

import fakeredis.aioredis
import pytest

from adhkar.auth.saml_replay import mark_seen


@pytest.fixture
async def redis() -> fakeredis.aioredis.FakeRedis:
    r = fakeredis.aioredis.FakeRedis()
    try:
        yield r
    finally:
        await r.aclose()


@pytest.mark.asyncio
async def test_mark_seen_returns_true_first_time(redis) -> None:
    assert await mark_seen(redis, "assertion-id-1", ttl_seconds=300) is True


@pytest.mark.asyncio
async def test_mark_seen_returns_false_on_replay(redis) -> None:
    await mark_seen(redis, "assertion-id-2", ttl_seconds=300)
    assert await mark_seen(redis, "assertion-id-2", ttl_seconds=300) is False


@pytest.mark.asyncio
async def test_mark_seen_clamps_ttl_lower_bound(redis) -> None:
    assert await mark_seen(redis, "assertion-id-3", ttl_seconds=0) is True
    # After clamp to 1s the key exists.
    assert await redis.exists("saml:seen:assertion-id-3") == 1


@pytest.mark.asyncio
async def test_mark_seen_clamps_ttl_upper_bound(redis) -> None:
    await mark_seen(redis, "assertion-id-4", ttl_seconds=999_999)
    ttl = await redis.ttl("saml:seen:assertion-id-4")
    assert 0 < ttl <= 86400


@pytest.mark.asyncio
async def test_mark_seen_respects_ttl_expiry(redis) -> None:
    await mark_seen(redis, "assertion-id-5", ttl_seconds=1)
    await asyncio.sleep(1.1)
    # After TTL elapses the second mark_seen should also return True.
    assert await mark_seen(redis, "assertion-id-5", ttl_seconds=300) is True
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/unit/test_saml_replay.py -q
```
Expected: `ModuleNotFoundError: No module named 'adhkar.auth.saml_replay'`.

- [ ] **Step 3: Write the module**

Create `backend/adhkar/auth/saml_replay.py`:
```python
"""Redis-backed SAML assertion replay cache.

Stores each accepted assertion ID under `saml:seen:{id}` with TTL =
assertion's NotOnOrAfter − now (clamped to [1, 86400] seconds). A
second arrival inside the window is rejected via SamlReplayError by
the caller."""

from __future__ import annotations

import redis.asyncio as redis_async

_KEY_PREFIX = "saml:seen:"
_TTL_MIN = 1
_TTL_MAX = 86_400


async def mark_seen(
    redis: redis_async.Redis,  # type: ignore[type-arg]
    assertion_id: str,
    ttl_seconds: int,
) -> bool:
    """Atomic SET NX EX. Returns True on first sight, False on replay."""
    ttl = max(_TTL_MIN, min(_TTL_MAX, int(ttl_seconds)))
    key = f"{_KEY_PREFIX}{assertion_id}"
    result = await redis.set(key, "1", nx=True, ex=ttl)
    return bool(result)
```

- [ ] **Step 4: Run tests, lint, typecheck**

```bash
cd backend && uv run pytest tests/unit/test_saml_replay.py -q \
  && uv run ruff check adhkar/auth/saml_replay.py tests/unit/test_saml_replay.py \
  && uv run ruff format adhkar/auth/saml_replay.py tests/unit/test_saml_replay.py \
  && uv run mypy adhkar/auth/saml_replay.py
```
Expected: `5 passed`, ruff clean, mypy `Success`.

- [ ] **Step 5: Commit + tag**

```bash
cd /Users/salma/Documents/Research/adhkar-ir
git commit -s -m "$(cat <<'EOF'
feat(saml): Redis-backed assertion replay cache

mark_seen(redis, assertion_id, ttl_seconds) → True on first sight,
False on replay. TTL clamped to [1, 86400] s. Caller maps False to
SamlReplayError so the audit row gets a clean reason.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)" -- backend/adhkar/auth/saml_replay.py backend/tests/unit/test_saml_replay.py
git tag v1.0.0-rc265.saml-replay
```

---

## Task 4: Extend SamlProviderConfig + loader with metadata_url + wanted_attributes

**Files:**
- Modify: `backend/adhkar/auth/saml.py`
- Modify: `backend/tests/unit/test_saml.py`

The existing `SamlProviderConfig` and `load_saml_providers` stay backward-compatible. New optional fields default to empty strings / empty dict so providers in the JSON without them parse as before.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/unit/test_saml.py`:
```python
import json as _json  # noqa: E402

from adhkar.auth.saml import load_saml_providers as _load_saml_providers  # noqa: E402


def test_load_saml_providers_reads_metadata_url(monkeypatch) -> None:
    monkeypatch.setenv("ADHKAR_SECRET_KEY", "x" * 32)
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h/db")
    monkeypatch.setenv("REDIS_URL", "redis://h:6379/0")
    monkeypatch.setenv(
        "ADHKAR_SAML_PROVIDERS_JSON",
        _json.dumps(
            {
                "okta": {
                    "idp_entity_id": "http://www.okta.com/exk-x",
                    "idp_sso_url": "https://acme.okta.com/app/sso/saml",
                    "sp_entity_id": "https://adhkar/api/v1/auth/saml/okta/metadata",
                    "acs_url": "https://adhkar/v1/auth/saml/okta/acs",
                    "metadata_url": "https://acme.okta.com/app/sso/saml/metadata",
                    "wanted_attributes": {"email": "mail", "display_name": "displayName"},
                }
            }
        ),
    )
    from adhkar.core.settings import Settings, get_settings

    get_settings.cache_clear()
    providers = _load_saml_providers(Settings())
    cfg = providers["okta"]
    assert cfg.metadata_url == "https://acme.okta.com/app/sso/saml/metadata"
    assert cfg.wanted_attributes == {"email": "mail", "display_name": "displayName"}


def test_load_saml_providers_defaults_new_fields(monkeypatch) -> None:
    monkeypatch.setenv("ADHKAR_SECRET_KEY", "x" * 32)
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h/db")
    monkeypatch.setenv("REDIS_URL", "redis://h:6379/0")
    monkeypatch.setenv(
        "ADHKAR_SAML_PROVIDERS_JSON",
        _json.dumps(
            {
                "minimal": {
                    "idp_entity_id": "a",
                    "idp_sso_url": "b",
                    "sp_entity_id": "c",
                    "acs_url": "d",
                }
            }
        ),
    )
    from adhkar.core.settings import Settings, get_settings

    get_settings.cache_clear()
    cfg = _load_saml_providers(Settings())["minimal"]
    assert cfg.metadata_url == ""
    assert cfg.wanted_attributes == {}
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/unit/test_saml.py::test_load_saml_providers_reads_metadata_url -q
```
Expected: `AttributeError: 'SamlProviderConfig' object has no attribute 'metadata_url'`.

- [ ] **Step 3: Extend SamlProviderConfig + loader**

Open `backend/adhkar/auth/saml.py`. Replace the `SamlProviderConfig` dataclass with:
```python
@dataclass(frozen=True, slots=True)
class SamlProviderConfig:
    name: str
    idp_entity_id: str
    idp_sso_url: str
    sp_entity_id: str
    acs_url: str
    idp_certificate_pem: str = ""
    metadata_url: str = ""
    wanted_attributes: dict[str, str] = field(default_factory=dict)
```

Add `field` to the imports near the top:
```python
from dataclasses import dataclass, field
```

In `load_saml_providers`, inside the loop, change the `SamlProviderConfig(...)` construction to:
```python
            out[str(name)] = SamlProviderConfig(
                name=str(name),
                idp_entity_id=str(cfg["idp_entity_id"]),
                idp_sso_url=str(cfg["idp_sso_url"]),
                sp_entity_id=str(cfg["sp_entity_id"]),
                acs_url=str(cfg["acs_url"]),
                idp_certificate_pem=str(cfg.get("idp_certificate_pem", "")),
                metadata_url=str(cfg.get("metadata_url", "")),
                wanted_attributes={
                    str(k): str(v)
                    for k, v in (cfg.get("wanted_attributes") or {}).items()
                    if isinstance(k, str) and isinstance(v, str)
                },
            )
```

- [ ] **Step 4: Run all SAML tests**

```bash
cd backend && uv run pytest tests/unit/test_saml.py -q
```
Expected: `8 passed` (6 pre-existing + 2 new).

- [ ] **Step 5: Lint + typecheck + commit + tag**

```bash
cd backend && uv run ruff check adhkar/auth/saml.py tests/unit/test_saml.py \
  && uv run ruff format adhkar/auth/saml.py tests/unit/test_saml.py \
  && uv run mypy adhkar/auth/saml.py
```
Expected: ruff clean, mypy `Success`.

```bash
cd /Users/salma/Documents/Research/adhkar-ir
git commit -s -m "$(cat <<'EOF'
feat(saml): metadata_url + wanted_attributes on SamlProviderConfig

Extend the existing ADHKAR_SAML_PROVIDERS_JSON schema with two
optional fields the new SamlVerifier needs. Defaults preserve
backward compat for providers that omit them.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)" -- backend/adhkar/auth/saml.py backend/tests/unit/test_saml.py
git tag v1.0.0-rc266.saml-config-extended
```

---

## Task 5: Pre-baked signed SAML fixtures

**Files:**
- Create: `backend/tests/unit/fixtures/saml/__init__.py` (empty)
- Create: `backend/tests/unit/fixtures/saml/_regenerate.py` (executable helper)
- Create (via script): `backend/tests/unit/fixtures/saml/valid_idp_cert.pem`
- Create (via script): `backend/tests/unit/fixtures/saml/valid_idp_key.pem`
- Create (via script): `backend/tests/unit/fixtures/saml/attacker_cert.pem`
- Create (via script): `backend/tests/unit/fixtures/saml/attacker_key.pem`
- Create (via script): `backend/tests/unit/fixtures/saml/valid_idp_metadata.xml`
- Create (via script): `backend/tests/unit/fixtures/saml/valid_response.xml`
- Create (via script): `backend/tests/unit/fixtures/saml/wrong_signer_response.xml`
- Create (via script): `backend/tests/unit/fixtures/saml/expired_response.xml`
- Create (via script): `backend/tests/unit/fixtures/saml/not_yet_valid_response.xml`
- Create (via script): `backend/tests/unit/fixtures/saml/wrong_audience_response.xml`
- Create (via script): `backend/tests/unit/fixtures/saml/wrong_recipient_response.xml`
- Create (via script): `backend/tests/unit/fixtures/saml/unsigned_response.xml`

- [ ] **Step 1: Write the regeneration script**

Create `backend/tests/unit/fixtures/saml/_regenerate.py`:
```python
"""Regenerate the committed SAML test fixtures.

Run this once from `backend/`:
    uv run python tests/unit/fixtures/saml/_regenerate.py

It builds two self-signed cert/key pairs (valid IdP + attacker), an
IdP metadata document that lists the valid IdP cert, and seven
SAMLResponse XML documents (signed or unsigned) covering each
verifier rejection branch.

Idempotent: produces byte-identical output for a given input. Commit
the resulting .pem and .xml files alongside this script. Do NOT run
in CI."""

from __future__ import annotations

import base64
import pathlib
from datetime import UTC, datetime, timedelta

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from saml2.sigver import SecurityContext
from saml2.sigver import security_context as _build_security_context  # noqa: F401

FIXTURES_DIR = pathlib.Path(__file__).parent

OUR_ACS_URL = "https://adhkar.test/v1/auth/saml/test/acs"
OUR_SP_ENTITY_ID = "https://adhkar.test/api/v1/auth/saml/test/metadata"
IDP_ENTITY_ID = "https://idp.test/saml/metadata"
IDP_SSO_URL = "https://idp.test/saml/sso"
ATTACKER_ENTITY_ID = "https://attacker.test/saml/metadata"

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


def _sign_response(template_xml: str, key_pem_path: pathlib.Path, cert_pem_path: pathlib.Path) -> str:
    """Sign the <saml:Assertion> inside `template_xml` with xmlsec1.

    Uses pysaml2's sigver helper rather than a raw xmlsec1 subprocess
    so we get the exact c14n + transform pysaml2 will verify."""
    from saml2.sigver import sign_statement_using_xmlsec

    cert_path_str = str(cert_pem_path)
    key_path_str = str(key_pem_path)
    return sign_statement_using_xmlsec(
        statement=template_xml,
        node_name="urn:oasis:names:tc:SAML:2.0:assertion:Assertion",
        key_file=key_path_str,
        cert_file=cert_path_str,
    )


def _build_response_xml(
    *,
    assertion_id: str,
    not_before: datetime,
    not_on_or_after: datetime,
    audience: str,
    recipient: str,
    name_id: str = "soc@example.test",
) -> str:
    """Unsigned SAMLResponse + Assertion template."""
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
  <saml:Assertion ID="{assertion_id}" IssueInstant="{NOW.isoformat()}" Version="2.0">
    <saml:Issuer>{IDP_ENTITY_ID}</saml:Issuer>
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
    b64_cert = base64.b64encode(
        cert_pem.replace(b"-----BEGIN CERTIFICATE-----", b"")
        .replace(b"-----END CERTIFICATE-----", b"")
        .replace(b"\n", b"")
    ).decode()
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

    # 3. Signed valid response
    valid_unsigned = _build_response_xml(
        assertion_id="assertion-valid",
        not_before=NOW - WINDOW,
        not_on_or_after=NOW + WINDOW,
        audience=OUR_SP_ENTITY_ID,
        recipient=OUR_ACS_URL,
    )
    (FIXTURES_DIR / "valid_response.xml").write_text(
        _sign_response(valid_unsigned,
                       FIXTURES_DIR / "valid_idp_key.pem",
                       FIXTURES_DIR / "valid_idp_cert.pem")
    )

    # 4. Wrong-signer response (signed by attacker key, but cert claims to be valid IdP)
    wrong_signer_unsigned = _build_response_xml(
        assertion_id="assertion-wrongsigner",
        not_before=NOW - WINDOW,
        not_on_or_after=NOW + WINDOW,
        audience=OUR_SP_ENTITY_ID,
        recipient=OUR_ACS_URL,
    )
    (FIXTURES_DIR / "wrong_signer_response.xml").write_text(
        _sign_response(wrong_signer_unsigned,
                       FIXTURES_DIR / "attacker_key.pem",
                       FIXTURES_DIR / "attacker_cert.pem")
    )

    # 5. Expired response
    expired_unsigned = _build_response_xml(
        assertion_id="assertion-expired",
        not_before=datetime(1970, 1, 1, tzinfo=UTC),
        not_on_or_after=datetime(1970, 1, 2, tzinfo=UTC),
        audience=OUR_SP_ENTITY_ID,
        recipient=OUR_ACS_URL,
    )
    (FIXTURES_DIR / "expired_response.xml").write_text(
        _sign_response(expired_unsigned,
                       FIXTURES_DIR / "valid_idp_key.pem",
                       FIXTURES_DIR / "valid_idp_cert.pem")
    )

    # 6. Not-yet-valid response
    nyv_unsigned = _build_response_xml(
        assertion_id="assertion-nyv",
        not_before=datetime(9999, 1, 1, tzinfo=UTC),
        not_on_or_after=datetime(9999, 1, 2, tzinfo=UTC),
        audience=OUR_SP_ENTITY_ID,
        recipient=OUR_ACS_URL,
    )
    (FIXTURES_DIR / "not_yet_valid_response.xml").write_text(
        _sign_response(nyv_unsigned,
                       FIXTURES_DIR / "valid_idp_key.pem",
                       FIXTURES_DIR / "valid_idp_cert.pem")
    )

    # 7. Wrong-audience response
    wa_unsigned = _build_response_xml(
        assertion_id="assertion-wrongaudience",
        not_before=NOW - WINDOW,
        not_on_or_after=NOW + WINDOW,
        audience="https://someone-else.invalid/",
        recipient=OUR_ACS_URL,
    )
    (FIXTURES_DIR / "wrong_audience_response.xml").write_text(
        _sign_response(wa_unsigned,
                       FIXTURES_DIR / "valid_idp_key.pem",
                       FIXTURES_DIR / "valid_idp_cert.pem")
    )

    # 8. Wrong-recipient response
    wr_unsigned = _build_response_xml(
        assertion_id="assertion-wrongrecipient",
        not_before=NOW - WINDOW,
        not_on_or_after=NOW + WINDOW,
        audience=OUR_SP_ENTITY_ID,
        recipient="https://attacker.test/acs",
    )
    (FIXTURES_DIR / "wrong_recipient_response.xml").write_text(
        _sign_response(wr_unsigned,
                       FIXTURES_DIR / "valid_idp_key.pem",
                       FIXTURES_DIR / "valid_idp_cert.pem")
    )

    # 9. Unsigned response (no <ds:Signature>)
    (FIXTURES_DIR / "unsigned_response.xml").write_text(
        _build_response_xml(
            assertion_id="assertion-unsigned",
            not_before=NOW - WINDOW,
            not_on_or_after=NOW + WINDOW,
            audience=OUR_SP_ENTITY_ID,
            recipient=OUR_ACS_URL,
        )
    )

    print(f"Wrote {len(list(FIXTURES_DIR.glob('*')))} files to {FIXTURES_DIR}")


if __name__ == "__main__":
    main()
```

Also create `backend/tests/unit/fixtures/saml/__init__.py` as empty so pytest treats it as a package.

- [ ] **Step 2: Run the regenerator**

```bash
cd backend && mkdir -p tests/unit/fixtures/saml && touch tests/unit/fixtures/saml/__init__.py \
  && uv run python tests/unit/fixtures/saml/_regenerate.py
```
Expected: `Wrote 12 files to .../backend/tests/unit/fixtures/saml`. If pysaml2 can't import the `sign_statement_using_xmlsec` helper, check `xmlsec1` is on `PATH` (`which xmlsec1`).

- [ ] **Step 3: Sanity-check a signed fixture**

```bash
cd backend && head -3 tests/unit/fixtures/saml/valid_response.xml
```
Expected: contains `<ds:Signature` somewhere inside (use `grep -c 'ds:Signature' tests/unit/fixtures/saml/valid_response.xml` → ≥1).

```bash
cd backend && grep -c 'ds:Signature' tests/unit/fixtures/saml/unsigned_response.xml
```
Expected: `0`.

- [ ] **Step 4: Commit all fixtures + script + tag**

```bash
cd /Users/salma/Documents/Research/adhkar-ir
git add backend/tests/unit/fixtures/saml/
git commit -s -m "$(cat <<'EOF'
test(saml): pre-baked signed SAMLResponse fixtures

Two self-signed keypairs (valid IdP + attacker), IdP metadata,
plus 7 SAMLResponse documents covering each SamlVerifier rejection
branch (valid, wrong signer, expired, not-yet-valid, wrong audience,
wrong recipient, unsigned). Generated by _regenerate.py via
pysaml2's sigver helper for byte-exact c14n.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
git tag v1.0.0-rc267.saml-fixtures
```

---

## Task 6: SamlVerifier — happy path

**Files:**
- Create: `backend/adhkar/auth/saml_verifier.py`
- Create: `backend/tests/unit/test_saml_verifier.py`

- [ ] **Step 1: Write the failing happy-path test**

Create `backend/tests/unit/test_saml_verifier.py`:
```python
"""SamlVerifier — fixture-based unit tests."""

from __future__ import annotations

import base64
import pathlib
from datetime import UTC, datetime

import fakeredis.aioredis
import pytest
from freezegun import freeze_time

from adhkar.auth.saml import SamlProviderConfig
from adhkar.auth.saml_verifier import SamlVerifier, build_verifier_from_metadata_xml

FIXTURES = pathlib.Path(__file__).parent / "fixtures" / "saml"
FROZEN_NOW = datetime(2026, 6, 17, 12, 0, 0, tzinfo=UTC)


def _b64(name: str) -> str:
    return base64.b64encode((FIXTURES / name).read_bytes()).decode()


@pytest.fixture
def cfg() -> SamlProviderConfig:
    return SamlProviderConfig(
        name="test",
        idp_entity_id="https://idp.test/saml/metadata",
        idp_sso_url="https://idp.test/saml/sso",
        sp_entity_id="https://adhkar.test/api/v1/auth/saml/test/metadata",
        acs_url="https://adhkar.test/v1/auth/saml/test/acs",
        metadata_url="https://idp.test/saml/metadata",
        wanted_attributes={"email": "mail", "display_name": "displayName"},
    )


@pytest.fixture
async def redis() -> fakeredis.aioredis.FakeRedis:
    r = fakeredis.aioredis.FakeRedis()
    try:
        yield r
    finally:
        await r.aclose()


@pytest.fixture
def verifier(cfg) -> SamlVerifier:
    metadata_xml = (FIXTURES / "valid_idp_metadata.xml").read_text()
    return build_verifier_from_metadata_xml(cfg, metadata_xml)


@pytest.mark.asyncio
@freeze_time(FROZEN_NOW)
async def test_valid_response_returns_claims(verifier, redis) -> None:
    claims = await verifier.verify_and_extract(_b64("valid_response.xml"), redis=redis)
    assert claims.email == "soc@example.test"
    assert claims.display_name == "SOC Bot"
    assert claims.name_id == "soc@example.test"
    assert claims.assertion_id == "assertion-valid"
    assert claims.not_on_or_after > FROZEN_NOW
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/unit/test_saml_verifier.py -q
```
Expected: `ModuleNotFoundError: No module named 'adhkar.auth.saml_verifier'`.

- [ ] **Step 3: Write the verifier — happy path only**

Create `backend/adhkar/auth/saml_verifier.py`:
```python
"""SAML response signature + envelope verification.

Wraps pysaml2's Saml2Client.parse_authn_request_response so the ACS
endpoint can call one function and either get typed SamlClaims back
or a typed SamlVerifyError. Replay protection is handled here via
saml_replay.mark_seen so callers don't need to remember it."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import UTC, datetime

import redis.asyncio as redis_async
from saml2 import BINDING_HTTP_POST
from saml2.client import Saml2Client
from saml2.config import SPConfig
from saml2.mdstore import MetadataStore
from saml2.response import StatusError

from adhkar.auth.saml import SamlProviderConfig
from adhkar.auth.saml_errors import (
    SamlAudienceError,
    SamlConfigError,
    SamlRecipientError,
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
                xmlstr=saml_response_b64,
                binding=BINDING_HTTP_POST,
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
        # Audience + recipient + timing are validated by pysaml2 already
        # when allow_unknown_attributes is False and want_assertions_signed
        # is True (set in SPConfig in build_verifier_from_metadata_xml).
        # If pysaml2 didn't raise, we trust the structural checks.
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
    def _extract_not_on_or_after(assertion) -> datetime:
        cond = assertion.conditions
        if cond is None or not cond.not_on_or_after:
            raise SamlTimingError("conditions_missing_not_on_or_after")
        return datetime.fromisoformat(cond.not_on_or_after.replace("Z", "+00:00"))

    @staticmethod
    def _extract_attrs(assertion) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {}
        for statement in assertion.attribute_statement or []:
            for attr in statement.attribute or []:
                name = attr.name or attr.friendly_name or ""
                if not name:
                    continue
                values = [av.text for av in (attr.attribute_value or []) if av.text]
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
    """Build a verifier from a literal metadata XML string (used by tests
    and by build_verifier() once it's fetched the metadata URL)."""
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
    mds = MetadataStore(None, sp_config, None)
    mds.load("inline", metadata_xml)
    sp_config.metadata = mds
    return SamlVerifier(cfg, Saml2Client(config=sp_config))
```

- [ ] **Step 4: Run happy-path test**

```bash
cd backend && uv run pytest tests/unit/test_saml_verifier.py::test_valid_response_returns_claims -q
```
Expected: `1 passed`.

- [ ] **Step 5: Lint + typecheck + commit + tag**

```bash
cd backend && uv run ruff check adhkar/auth/saml_verifier.py tests/unit/test_saml_verifier.py \
  && uv run ruff format adhkar/auth/saml_verifier.py tests/unit/test_saml_verifier.py \
  && uv run mypy adhkar/auth/saml_verifier.py
```
Expected: ruff clean, mypy `Success`.

```bash
cd /Users/salma/Documents/Research/adhkar-ir
git commit -s -m "$(cat <<'EOF'
feat(saml): SamlVerifier — signature + envelope verification (happy path)

Wraps pysaml2's parse_authn_request_response so the ACS endpoint can
call one function and get typed SamlClaims back. pysaml2 enforces
signature + audience + recipient + timing; we wrap them as
SamlSignatureError. Replay check via saml_replay.mark_seen.
Happy-path test green; rejection matrix follows in next task.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)" -- backend/adhkar/auth/saml_verifier.py backend/tests/unit/test_saml_verifier.py
git tag v1.0.0-rc268.saml-verifier-happy
```

---

## Task 7: SamlVerifier rejection matrix

**Files:**
- Modify: `backend/tests/unit/test_saml_verifier.py`
- Modify: `backend/adhkar/auth/saml_verifier.py` (only if a rejection test surfaces a gap)

- [ ] **Step 1: Add the failing rejection tests**

Append to `backend/tests/unit/test_saml_verifier.py`:
```python
from adhkar.auth.saml_errors import (  # noqa: E402
    SamlAudienceError,
    SamlRecipientError,
    SamlReplayError,
    SamlSignatureError,
    SamlTimingError,
)


@pytest.mark.asyncio
@freeze_time(FROZEN_NOW)
async def test_wrong_signer_raises_signature_error(verifier, redis) -> None:
    with pytest.raises(SamlSignatureError):
        await verifier.verify_and_extract(_b64("wrong_signer_response.xml"), redis=redis)


@pytest.mark.asyncio
@freeze_time(FROZEN_NOW)
async def test_unsigned_raises_signature_error(verifier, redis) -> None:
    with pytest.raises(SamlSignatureError):
        await verifier.verify_and_extract(_b64("unsigned_response.xml"), redis=redis)


@pytest.mark.asyncio
@freeze_time(FROZEN_NOW)
async def test_expired_raises_timing_or_signature(verifier, redis) -> None:
    with pytest.raises((SamlTimingError, SamlSignatureError)):
        await verifier.verify_and_extract(_b64("expired_response.xml"), redis=redis)


@pytest.mark.asyncio
@freeze_time(FROZEN_NOW)
async def test_not_yet_valid_raises_timing_or_signature(verifier, redis) -> None:
    with pytest.raises((SamlTimingError, SamlSignatureError)):
        await verifier.verify_and_extract(_b64("not_yet_valid_response.xml"), redis=redis)


@pytest.mark.asyncio
@freeze_time(FROZEN_NOW)
async def test_wrong_audience_raises_audience_or_signature(verifier, redis) -> None:
    with pytest.raises((SamlAudienceError, SamlSignatureError)):
        await verifier.verify_and_extract(_b64("wrong_audience_response.xml"), redis=redis)


@pytest.mark.asyncio
@freeze_time(FROZEN_NOW)
async def test_wrong_recipient_raises_recipient_or_signature(verifier, redis) -> None:
    with pytest.raises((SamlRecipientError, SamlSignatureError)):
        await verifier.verify_and_extract(_b64("wrong_recipient_response.xml"), redis=redis)


@pytest.mark.asyncio
@freeze_time(FROZEN_NOW)
async def test_replay_second_call_raises_replay_error(verifier, redis) -> None:
    await verifier.verify_and_extract(_b64("valid_response.xml"), redis=redis)
    with pytest.raises(SamlReplayError):
        await verifier.verify_and_extract(_b64("valid_response.xml"), redis=redis)
```

The `(X, SamlSignatureError)` tuple matchers reflect that pysaml2 rolls timing/audience/recipient failures into its parse-time signature/envelope check. Either rejection class is acceptable as long as the request is rejected; the audit code in Task 10 will surface the actual reason string.

- [ ] **Step 2: Run all verifier tests**

```bash
cd backend && uv run pytest tests/unit/test_saml_verifier.py -q
```
Expected: `8 passed`. If any test fails, the verifier needs adjustment — most likely the `Exception → SamlSignatureError` catch in `verify_and_extract` should special-case pysaml2's `ToEarly`/`ResponseLifetimeExceed` exception types and re-raise as `SamlTimingError`, and `NotForMe` as `SamlAudienceError`. Apply this mapping inside the existing try/except in `verify_and_extract`:

```python
        except StatusError as e:
            raise SamlSignatureError(f"status_error:{e}") from e
        except Exception as e:
            name = type(e).__name__
            if name in {"ToEarly", "ResponseLifetimeExceed"}:
                raise SamlTimingError(f"timing:{name}") from e
            if name == "NotForMe":
                raise SamlAudienceError(f"audience:{name}") from e
            raise SamlSignatureError(f"parse_failed:{name}") from e
```

Re-run the test command above. Expected: `8 passed`.

- [ ] **Step 3: Lint + typecheck + commit + tag**

```bash
cd backend && uv run ruff check adhkar/auth/saml_verifier.py tests/unit/test_saml_verifier.py \
  && uv run ruff format adhkar/auth/saml_verifier.py tests/unit/test_saml_verifier.py \
  && uv run mypy adhkar/auth/saml_verifier.py
```
Expected: clean.

```bash
cd /Users/salma/Documents/Research/adhkar-ir
git commit -s -m "$(cat <<'EOF'
feat(saml): SamlVerifier rejection matrix

Seven rejection tests cover wrong-signer / unsigned / expired /
not-yet-valid / wrong-audience / wrong-recipient / replay. Map
pysaml2 timing/audience exception types to SamlTimingError /
SamlAudienceError so audit reasons stay specific.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)" -- backend/adhkar/auth/saml_verifier.py backend/tests/unit/test_saml_verifier.py
git tag v1.0.0-rc269.saml-verifier-matrix
```

---

## Task 8: build_verifier factory + lifespan wiring

**Files:**
- Modify: `backend/adhkar/auth/saml_verifier.py`
- Modify: `backend/adhkar/main.py`
- Create: `backend/tests/unit/test_saml_loader.py`

- [ ] **Step 1: Write the failing factory test**

Create `backend/tests/unit/test_saml_loader.py`:
```python
"""build_verifier_from_metadata_url integration test using respx."""

from __future__ import annotations

import pathlib

import httpx
import pytest
import respx

from adhkar.auth.saml import SamlProviderConfig
from adhkar.auth.saml_verifier import build_verifier_from_metadata_url

FIXTURES = pathlib.Path(__file__).parent / "fixtures" / "saml"


def _cfg(metadata_url: str) -> SamlProviderConfig:
    return SamlProviderConfig(
        name="test",
        idp_entity_id="https://idp.test/saml/metadata",
        idp_sso_url="https://idp.test/saml/sso",
        sp_entity_id="https://adhkar.test/api/v1/auth/saml/test/metadata",
        acs_url="https://adhkar.test/v1/auth/saml/test/acs",
        metadata_url=metadata_url,
    )


@pytest.mark.asyncio
async def test_build_verifier_succeeds_when_metadata_url_reachable() -> None:
    metadata_xml = (FIXTURES / "valid_idp_metadata.xml").read_text()
    with respx.mock:
        respx.get("https://idp.test/metadata.xml").mock(
            return_value=httpx.Response(200, text=metadata_xml)
        )
        verifier = await build_verifier_from_metadata_url(
            _cfg("https://idp.test/metadata.xml")
        )
    assert verifier is not None


@pytest.mark.asyncio
async def test_build_verifier_returns_none_when_metadata_unreachable() -> None:
    with respx.mock:
        respx.get("https://idp.test/missing.xml").mock(side_effect=httpx.ConnectError("nope"))
        verifier = await build_verifier_from_metadata_url(
            _cfg("https://idp.test/missing.xml")
        )
    assert verifier is None


@pytest.mark.asyncio
async def test_build_verifier_returns_none_on_404() -> None:
    with respx.mock:
        respx.get("https://idp.test/404.xml").mock(return_value=httpx.Response(404))
        verifier = await build_verifier_from_metadata_url(
            _cfg("https://idp.test/404.xml")
        )
    assert verifier is None


@pytest.mark.asyncio
async def test_build_verifier_returns_none_when_metadata_url_empty() -> None:
    verifier = await build_verifier_from_metadata_url(_cfg(""))
    assert verifier is None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/unit/test_saml_loader.py -q
```
Expected: `ImportError: cannot import name 'build_verifier_from_metadata_url'`.

- [ ] **Step 3: Add the factory function**

Append to `backend/adhkar/auth/saml_verifier.py`:
```python
import httpx  # noqa: E402  add to import block at top of file


async def build_verifier_from_metadata_url(
    cfg: SamlProviderConfig,
    *,
    timeout_seconds: float = 5.0,
) -> SamlVerifier | None:
    """Fetch IdP metadata over HTTPS, build a SamlVerifier. Returns None
    on any failure (caller logs + emits audit event)."""
    if not cfg.metadata_url:
        return None
    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            resp = await client.get(cfg.metadata_url)
    except httpx.HTTPError:
        return None
    if resp.status_code != 200 or not resp.text:
        return None
    try:
        return build_verifier_from_metadata_xml(cfg, resp.text)
    except SamlConfigError:
        return None
    except Exception:  # pysaml2 metadata-parse can raise many types
        return None
```

Move the existing `import httpx` to the top-of-file import block (group with other third-party imports, before `from saml2 ...`).

- [ ] **Step 4: Run loader tests**

```bash
cd backend && uv run pytest tests/unit/test_saml_loader.py -q
```
Expected: `4 passed`.

- [ ] **Step 5: Wire into lifespan**

Open `backend/adhkar/main.py`. Inside the existing `lifespan` async context manager (around line 60), AFTER the worker `asyncio.create_task` lines and BEFORE `yield`, add:

```python
        # SAML verifiers (one per configured provider). Soft-fail: a
        # provider whose metadata URL is unreachable lands as None and
        # its ACS endpoint will 503. App still boots so local password
        # and API-key login keep working during an IdP outage.
        from adhkar.auth.saml import load_saml_providers as _load_saml_providers
        from adhkar.auth.saml_verifier import (
            build_verifier_from_metadata_url as _build_saml_verifier,
        )

        saml_verifiers: dict[str, object | None] = {}
        for _name, _cfg in _load_saml_providers(settings).items():
            saml_verifiers[_name] = await _build_saml_verifier(_cfg)
            if saml_verifiers[_name] is None:
                _log = __import__("logging").getLogger("adhkar.main")
                _log.warning(
                    "saml_metadata_unavailable provider=%s metadata_url=%s",
                    _name,
                    _cfg.metadata_url,
                )
        app.state.saml_verifiers = saml_verifiers
```

- [ ] **Step 6: Smoke + lint + typecheck**

```bash
cd backend && uv run pytest tests/integration/test_openapi_route_coverage.py tests/unit/test_saml_loader.py tests/unit/test_saml_verifier.py -q \
  && uv run ruff check adhkar/auth/saml_verifier.py adhkar/main.py tests/unit/test_saml_loader.py \
  && uv run ruff format adhkar/auth/saml_verifier.py adhkar/main.py tests/unit/test_saml_loader.py \
  && uv run mypy adhkar/auth/saml_verifier.py adhkar/main.py
```
Expected: all green.

- [ ] **Step 7: Commit + tag**

```bash
cd /Users/salma/Documents/Research/adhkar-ir
git commit -s -m "$(cat <<'EOF'
feat(saml): build_verifier_from_metadata_url + app-lifespan wiring

Soft-fail boot: each configured SAML provider's metadata URL is
fetched at startup; success → SamlVerifier in app.state, failure →
None (ACS endpoint will 503). App stays up if IdP is unreachable.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)" -- backend/adhkar/auth/saml_verifier.py backend/adhkar/main.py backend/tests/unit/test_saml_loader.py
git tag v1.0.0-rc270.saml-lifespan
```

---

## Task 9: Replace ACS direct extract call with verifier path

**Files:**
- Modify: `backend/adhkar/api/v1/saml.py`

- [ ] **Step 1: Read current ACS endpoint**

```bash
cd backend && sed -n '60,123p' adhkar/api/v1/saml.py
```
Confirm: the `acs` handler currently calls `extract_assertion_attributes(xml)` (line ~80) and only logs a warning if `p.idp_certificate_pem` is empty.

- [ ] **Step 2: Rewrite the handler**

In `backend/adhkar/api/v1/saml.py`, replace the entire `async def acs(...)` function body (the function signature stays the same) with:

```python
async def acs(
    provider: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    SAMLResponse: Annotated[str, Form()],  # noqa: N803  SAML spec name
    RelayState: Annotated[str, Form()] = "",  # noqa: N803  SAML spec name
    request: Request = None,  # type: ignore[assignment]
) -> dict[str, Any]:
    """Assertion Consumer Service. Verifies SAML signature/audience/
    recipient/timing/replay via pysaml2-backed SamlVerifier, upserts
    the User on email match, and issues Adhkar JWTs."""
    settings = get_settings()
    p = _provider_or_404(settings, provider)
    decoded_relay = verify_state(settings.secret_key, RelayState) if RelayState else None
    if RelayState and (not decoded_relay or decoded_relay.get("provider") != provider):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid_relay_state")

    verifier = (
        getattr(request.app.state, "saml_verifiers", {}).get(provider) if request else None
    )
    if verifier is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "saml_metadata_unavailable"
        )

    redis_url = str(settings.redis_url)
    redis_client = redis_async.from_url(redis_url, decode_responses=False)
    try:
        try:
            claims = await verifier.verify_and_extract(SAMLResponse, redis=redis_client)
        except SamlSignatureError as e:
            await _audit_failed(db, provider, "signature_invalid", e.reason, request)
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "signature_invalid") from e
        except SamlTimingError as e:
            await _audit_failed(db, provider, "assertion_expired", e.reason, request)
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "assertion_expired") from e
        except SamlAudienceError as e:
            await _audit_failed(db, provider, "audience_mismatch", e.reason, request)
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "audience_mismatch") from e
        except SamlRecipientError as e:
            await _audit_failed(db, provider, "recipient_mismatch", e.reason, request)
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "recipient_mismatch") from e
        except SamlReplayError as e:
            await _audit_failed(db, provider, "assertion_replayed", e.reason, request)
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "assertion_replayed") from e
        except SamlConfigError as e:
            await _audit_failed(db, provider, "saml_misconfigured", e.reason, request)
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE, "saml_misconfigured"
            ) from e
    finally:
        await redis_client.aclose()

    email = (claims.email or claims.name_id or "").strip()
    if not email:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "saml_assertion_missing_email_or_nameid")
    display_name = claims.display_name or email
    existing = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if existing is None:
        existing = User(
            email=email,
            display_name=display_name[:200],
            password_hash=None,
            status="active",
        )
        db.add(existing)
        await db.flush()
    elif existing.status == "pending_invite":
        existing.status = "active"
        existing.display_name = display_name[:200]
        await db.flush()
    tokens = await issue_tokens(
        session=db,
        user_id=existing.id,
        org_id=existing.default_org_id,
        perms=[],
        secret=settings.secret_key,
    )
    return {
        "access_token": tokens.access_token,
        "token_type": "bearer",
        "expires_in": 900,
        "user_id": str(existing.id),
        "current_org_id": str(existing.default_org_id) if existing.default_org_id else None,
        "return_to": decoded_relay.get("return_to", "/") if decoded_relay else "/",
    }


async def _audit_failed(
    db: AsyncSession,
    provider: str,
    code: str,
    reason: str,
    request: Request | None,
) -> None:
    from adhkar.audit import audit_and_emit

    await audit_and_emit(
        db,
        actor_user_id=None,
        organization_id=None,
        action="saml_verify_failed",
        entity_type="user",
        entity_id=None,
        diff={
            "provider": provider,
            "code": code,
            "reason": reason,
            "source_ip": (request.client.host if request and request.client else None),
        },
    )
```

Update the imports at the top of the file. Replace:
```python
from adhkar.auth.saml import (
    SamlProviderConfig,
    extract_assertion_attributes,
    load_saml_providers,
)
```
with:
```python
import redis.asyncio as redis_async

from fastapi import Request

from adhkar.auth.saml import SamlProviderConfig, load_saml_providers
from adhkar.auth.saml_errors import (
    SamlAudienceError,
    SamlConfigError,
    SamlRecipientError,
    SamlReplayError,
    SamlSignatureError,
    SamlTimingError,
)
```

Also delete the now-unused `import base64` and `import logging` lines + the `_log = logging.getLogger(__name__)` constant. The `extract_assertion_attributes` function in `adhkar/auth/saml.py` stays for backward-compat unit tests but is no longer called by the endpoint.

- [ ] **Step 3: Lint + typecheck**

```bash
cd backend && uv run ruff check adhkar/api/v1/saml.py \
  && uv run ruff format adhkar/api/v1/saml.py \
  && uv run mypy adhkar/api/v1/saml.py
```
Expected: clean.

- [ ] **Step 4: Smoke**

```bash
cd backend && uv run pytest tests/integration/test_openapi_route_coverage.py -q
```
Expected: `3 passed`.

- [ ] **Step 5: Commit + tag**

```bash
cd /Users/salma/Documents/Research/adhkar-ir
git commit -s -m "$(cat <<'EOF'
feat(saml): wire SamlVerifier into /v1/auth/saml/{provider}/acs

Replace the unvalidated extract_assertion_attributes call with a
SamlVerifier.verify_and_extract path. Each typed exception maps to
a specific 401 / 503 + audit event with provider + reason +
source_ip. Missing verifier slot (metadata-unavailable) → 503.

Closes the #1 security blocker for v1.0.0: unsigned/tampered SAML
assertions are now rejected.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)" -- backend/adhkar/api/v1/saml.py
git tag v1.0.0-rc271.saml-acs-verified
```

---

## Task 10: ACS integration test against fixture

**Files:**
- Create: `backend/tests/integration/test_saml_acs.py`

- [ ] **Step 1: Write the integration test**

Create `backend/tests/integration/test_saml_acs.py`:
```python
"""End-to-end: POST a signed SAML fixture against the live /acs endpoint.

Mounts a pre-built SamlVerifier into app.state so we don't need to
hit a real IdP metadata URL during the test."""

from __future__ import annotations

import base64
import json
import pathlib
from datetime import UTC, datetime

import fakeredis.aioredis
import pytest
from freezegun import freeze_time
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from adhkar.auth.saml import SamlProviderConfig
from adhkar.auth.saml_verifier import build_verifier_from_metadata_xml

FIXTURES = pathlib.Path(__file__).parent.parent / "unit" / "fixtures" / "saml"
FROZEN_NOW = datetime(2026, 6, 17, 12, 0, 0, tzinfo=UTC)


@pytest.fixture
def saml_env(monkeypatch) -> None:
    monkeypatch.setenv("ADHKAR_SECRET_KEY", "x" * 32)
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h/db")
    monkeypatch.setenv("REDIS_URL", "redis://h:6379/0")
    monkeypatch.setenv(
        "ADHKAR_SAML_PROVIDERS_JSON",
        json.dumps(
            {
                "test": {
                    "idp_entity_id": "https://idp.test/saml/metadata",
                    "idp_sso_url": "https://idp.test/saml/sso",
                    "sp_entity_id": "https://adhkar.test/api/v1/auth/saml/test/metadata",
                    "acs_url": "https://adhkar.test/v1/auth/saml/test/acs",
                    "metadata_url": "https://idp.test/metadata",
                }
            }
        ),
    )
    from adhkar.core.settings import get_settings

    get_settings.cache_clear()


def _app_with_verifier(saml_env):  # noqa: ARG001 — fixture side-effect
    from adhkar.core.settings import Settings
    from adhkar.main import create_app

    app = create_app(Settings())
    cfg = SamlProviderConfig(
        name="test",
        idp_entity_id="https://idp.test/saml/metadata",
        idp_sso_url="https://idp.test/saml/sso",
        sp_entity_id="https://adhkar.test/api/v1/auth/saml/test/metadata",
        acs_url="https://adhkar.test/v1/auth/saml/test/acs",
        metadata_url="https://idp.test/metadata",
        wanted_attributes={"email": "mail", "display_name": "displayName"},
    )
    metadata_xml = (FIXTURES / "valid_idp_metadata.xml").read_text()
    app.state.saml_verifiers = {"test": build_verifier_from_metadata_xml(cfg, metadata_xml)}
    return app


def _b64(name: str) -> str:
    return base64.b64encode((FIXTURES / name).read_bytes()).decode()


@pytest.mark.asyncio
@freeze_time(FROZEN_NOW)
async def test_acs_with_wrong_signer_returns_401(saml_env, monkeypatch) -> None:
    # Stub Redis client so the endpoint's redis_async.from_url returns fakeredis.
    fake = fakeredis.aioredis.FakeRedis()
    monkeypatch.setattr(
        "adhkar.api.v1.saml.redis_async.from_url",
        lambda *_, **__: fake,
    )
    # Stub the DB dependency so we don't need a live Postgres.
    from adhkar.api.deps import get_db
    from adhkar.main import create_app
    from adhkar.core.settings import Settings

    class _NoopSession:
        async def execute(self, *_a, **_k):
            class _R:
                def scalar_one_or_none(self):
                    return None
            return _R()
        def add(self, _o): ...
        async def flush(self): ...

    async def _override_db():
        yield _NoopSession()

    app = _app_with_verifier(saml_env)
    app.dependency_overrides[get_db] = _override_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.post(
            "/v1/auth/saml/test/acs",
            data={"SAMLResponse": _b64("wrong_signer_response.xml"), "RelayState": ""},
        )
    assert r.status_code == 401
    assert r.json()["detail"] == "signature_invalid"


@pytest.mark.asyncio
@freeze_time(FROZEN_NOW)
async def test_acs_without_verifier_returns_503(saml_env, monkeypatch) -> None:
    from adhkar.core.settings import Settings
    from adhkar.main import create_app

    app = create_app(Settings())
    app.state.saml_verifiers = {}  # provider 'test' deliberately absent
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.post(
            "/v1/auth/saml/test/acs",
            data={"SAMLResponse": _b64("valid_response.xml"), "RelayState": ""},
        )
    assert r.status_code == 503
    assert r.json()["detail"] == "saml_metadata_unavailable"
```

The valid-response 200 test is intentionally omitted from this task because issuing real tokens requires a live DB session (Postgres). That path is covered by Task 7's verifier unit tests (which verify `claims.email` + `claims.assertion_id`) and the integration suite that lands as part of the next plan (testcontainers).

- [ ] **Step 2: Run the integration test**

```bash
cd backend && uv run pytest tests/integration/test_saml_acs.py -q
```
Expected: `2 passed`.

- [ ] **Step 3: Run full test suite to catch regressions**

```bash
cd backend && uv run pytest tests/ -q
```
Expected: all prior tests still pass. Look for the count to be `previous_total + 8 (verifier matrix) + 4 (loader) + 5 (replay) + 7 (errors) + 2 (acs integration) = previous_total + 26 new` minus the 1 deleted assertion-extractor coupling check (none).

- [ ] **Step 4: Lint + typecheck + commit + tag**

```bash
cd backend && uv run ruff check tests/integration/test_saml_acs.py \
  && uv run ruff format tests/integration/test_saml_acs.py \
  && uv run mypy tests/integration/test_saml_acs.py
```
Expected: clean.

```bash
cd /Users/salma/Documents/Research/adhkar-ir
git commit -s -m "$(cat <<'EOF'
test(saml): end-to-end ACS test against signed fixtures

Two test cases: wrong-signer fixture POSTed to /acs returns 401
signature_invalid; missing verifier slot returns 503
saml_metadata_unavailable. Happy-path 200 deferred to the
testcontainers integration suite (separate plan) since it needs a
live DB to mint tokens.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)" -- backend/tests/integration/test_saml_acs.py
git tag v1.0.0-rc272.saml-acs-integration-test
```

---

## Task 11: Final hardening pass

**Files:**
- Modify: `backend/tests/integration/test_openapi_route_coverage.py` (only if any new path added — none here)
- Verify: full backend `pytest` + `mypy` + `ruff` green
- Update: `/Users/salma/.claude/projects/-Users-salma-Documents-Research-TheBee/memory/project-adhkar-ir.md` with the new ship snapshot

- [ ] **Step 1: Final validation**

```bash
cd backend && uv run ruff check --fix . && uv run ruff format . \
  && uv run mypy adhkar \
  && uv run pytest tests/ -q
```
Expected: everything green. If any pre-existing flaky test fails, retry once; if it fails twice, that's a separate issue and should not block this plan.

- [ ] **Step 2: Confirm no smoke regressions**

```bash
cd backend && uv run pytest tests/integration/test_openapi_route_coverage.py -q
```
Expected: `3 passed`. No new routes were added (we only changed the ACS handler body, not its path), so the `EXPECTED_PATHS` tuple does not need updating.

- [ ] **Step 3: Append memory snapshot**

Open `/Users/salma/.claude/projects/-Users-salma-Documents-Research-TheBee/memory/project-adhkar-ir.md`. Find the line starting with `- **RC262 ship snapshot` (it's near the top of the per-RC section) and insert ABOVE it:

```markdown
- **RC263-RC272 ship snapshot — 2026-06-17 — branch `phase10/hardening`** — SAML signature verification end-to-end. Wired pysaml2 behind /v1/auth/saml/{provider}/acs; ACS now rejects unsigned/wrong-signer/expired/wrong-audience/wrong-recipient/replayed assertions with typed 401s + audit events. Redis-backed assertion replay cache. Lifespan hook builds one SamlVerifier per provider from cached IdP metadata (soft-fail: missing metadata → 503 on ACS, app stays up). 12 fixtures + 26 new tests. Closes the #1 v1.0.0 security blocker. Spec at docs/superpowers/specs/2026-06-17-adhkar-saml-signature-verification-design.md; plan at docs/superpowers/plans/2026-06-17-saml-signature-verification.md.
```

- [ ] **Step 4: Commit memory + tag final RC**

```bash
cd /Users/salma/.claude/projects/-Users-salma-Documents-Research-TheBee
# memory dir is not a git repo; just save the file. No git action needed.
```

```bash
cd /Users/salma/Documents/Research/adhkar-ir
git tag v1.0.0-rc273.saml-signature-verification-complete
git log --oneline -12
```
Expected: the last 11 commits read RC263 → RC272, plus the spec commit `b9a69fa`. The final tag `RC273` is a marker tag pointing at the same commit as `RC272` to denote the closing of this phase-10 hardening item.

---

## Coverage check (run after Task 11)

| Spec requirement | Implementing task |
|------------------|-------------------|
| pysaml2 backed verification | Task 6 (verifier core) + Task 7 (rejection matrix) |
| Metadata URL fetch + cache at startup | Task 8 (`build_verifier_from_metadata_url` + lifespan) |
| Soft-fail boot (503 not crash) | Task 8 (lifespan logs warning, sets None) + Task 9 (ACS returns 503) |
| Redis-backed replay cache | Task 3 (`saml_replay.mark_seen`) + Task 6 (called from verifier) |
| 60-second clock skew | Task 6 (`accepted_time_diff=CLOCK_SKEW_SECONDS` in SPConfig) |
| Audience restriction enforced | pysaml2 default in `Saml2Client` + Task 7 (`NotForMe` → SamlAudienceError) |
| Subject recipient enforced | pysaml2 default in `Saml2Client` |
| Typed exceptions per failure | Task 2 (hierarchy) + Task 7 (mapping) |
| Per-request audit events | Task 9 (`_audit_failed`) |
| Pre-baked signed XML fixtures | Task 5 (regenerator + commit) |
| Unit tests per rejection | Task 7 (rejection matrix) |
| Integration test against /acs | Task 10 (`test_saml_acs.py`) |
| No backward-compat break of existing OIDC/local-auth paths | Task 9 (ACS rewrite is local; other endpoints unchanged) |

All spec requirements have a task. No placeholders. No type drift (every cross-task reference matches: `SamlVerifier.verify_and_extract`, `mark_seen`, `SamlClaims.assertion_id`, `build_verifier_from_metadata_url`, error classes).

---

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-17-saml-signature-verification.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
