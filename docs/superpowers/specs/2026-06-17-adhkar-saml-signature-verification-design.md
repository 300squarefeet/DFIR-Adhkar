# SAML Signature Verification — Design

**Status:** Approved 2026-06-17
**Phase:** 10 (Hardening)
**Blocker for:** v1.0.0 production release

## Problem

`backend/adhkar/auth/saml.py:11-12` declares:

> "signature verification is intentionally NOT here — pysaml2 handles that in the live IdP path"

The "live IdP path" was never wired. `verify_saml_response` in `backend/adhkar/api/v1/saml.py` is a pluggable hook with no production implementation. Today the SAML ACS endpoint `POST /v1/auth/saml/{provider}/acs` accepts assertions without verifying their XML-DSig signature — anyone who can POST a crafted SAML response can log in as any user the IdP would have asserted.

This is the #1 security blocker for shipping `v1.0.0`.

## Goal

Replace the empty `verify_saml_response` hook with a `pysaml2`-backed implementation that enforces, at minimum:

1. Valid XML-DSig signature on the SAML Assertion, against the IdP's published signing certificate.
2. Time-bounded validity (`NotBefore` / `NotOnOrAfter`) with 60-second clock skew tolerance.
3. Audience restriction (`AudienceRestriction` must include our SP entity ID).
4. Subject confirmation recipient match (`SubjectConfirmation.Recipient` must equal our ACS URL).
5. Replay protection (per-assertion-ID single-use within the assertion's validity window).

After this lands, the only login surfaces that bypass signature verification are local password and API-key — both intentional.

## Non-goals (this iteration)

- SAML Single Logout (SLO).
- Encrypted assertions (`<EncryptedAssertion>`).
- Background metadata refresh — operator restarts the app to pick up IdP key rotation. Documented as a known limitation.
- IdP-initiated SSO — we stay SP-initiated only.

## Architectural decisions (locked)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Library | **pysaml2** | Mature; handles metadata, signature, audience, recipient, timing in one place. Memory already references it. Sync API — wrap in `run_in_threadpool` at the ACS endpoint. |
| IdP metadata source | **URL, fetched + cached at app startup** | Operator sets `ADHKAR_SAML_<provider>_METADATA_URL`. Restart picks up key rotation. Matches existing OIDC discovery pattern. |
| Boot failure mode | **Soft fail (503 on SAML ACS only)** | SIRP must stay up during incidents even if IdP is down. Local password + API-key login keep working; `/readyz` stays green. We log + audit. |
| Replay protection | **Redis-cached assertion ID, TTL = `NotOnOrAfter − now`** | Uses Redis already in stack. Spans multi-replica deploys. Closes the 5-minute replay window pysaml2 alone cannot. |
| Test fidelity | **Pre-baked signed XML fixtures** | Fast, deterministic, no docker. Same code paths as a live IdP. A regeneration script ships for maintainers. |

## File structure

| File | Status | Responsibility |
|------|--------|----------------|
| `backend/adhkar/auth/saml.py` | **modify** | Extend `SamlProviderConfig` with `metadata_url`, `our_entity_id`, `our_acs_url`, `wanted_attributes`. Add `load_saml_providers(settings) -> dict[str, SamlProviderConfig]` that reads env vars. Keep `_extract_attributes` for parser-only unit tests. |
| `backend/adhkar/auth/saml_verifier.py` | **create** | `build_verifier(provider_cfg) -> SamlVerifier \| None` and class `SamlVerifier` with `verify_and_extract(saml_response_b64: str, relay_state: str \| None) -> SamlClaims`. Owns one `pysaml2.client_base.Base` per provider. Raises typed exceptions. |
| `backend/adhkar/auth/saml_replay.py` | **create** | Single function `mark_seen(assertion_id: str, ttl_seconds: int) -> bool`. `True` on first sight, `False` on replay. ~20 LOC over an injected `redis.asyncio.Redis`. |
| `backend/adhkar/auth/saml_errors.py` | **create** | `SamlSignatureError`, `SamlTimingError`, `SamlAudienceError`, `SamlRecipientError`, `SamlReplayError`, `SamlConfigError` — all subclass `SamlVerifyError`. No logic, just exception types so the ACS endpoint can map them. |
| `backend/adhkar/api/v1/saml.py` | **modify** | Replace the empty `verify_saml_response` hook body with a call into `request.app.state.saml_verifiers[provider].verify_and_extract(...)` via `run_in_threadpool`. Map typed exceptions to HTTP status + audit event. Handle missing-verifier slot → 503. |
| `backend/adhkar/main.py` | **modify** | In the existing FastAPI lifespan: call `load_saml_providers(settings)`, then for each provider call `build_verifier()`. Store result in `app.state.saml_verifiers: dict[str, SamlVerifier \| None]`. Log + emit audit event on each failure. |
| `pyproject.toml` | **modify** | Add `pysaml2 = "^7.5"` to `[project.dependencies]`. Document the `xmlsec1` system package requirement in `README.md` (separate doc PR, not in scope here). |

## Data flow

```
App startup
  └── lifespan
       └── load_saml_providers(settings)              ← reads ADHKAR_SAML_* env vars
            └── for each provider:
                  └── build_verifier(cfg)
                       ├── httpx.get(cfg.metadata_url) ← timeout 5s
                       ├── pysaml2 MetadataStore.load_metadata_from_string(xml)
                       ├── Build pysaml2 client with our_entity_id, our_acs_url
                       └── return SamlVerifier(client)   OR  None  on any failure
                            (None: log warning, audit event saml.metadata_unavailable)

Request: POST /v1/auth/saml/{provider}/acs
  └── look up verifier in app.state.saml_verifiers[provider]
       ├── None  → 503 {"error":"saml_metadata_unavailable","provider":provider}
       └── present → run_in_threadpool(verifier.verify_and_extract, saml_response_b64, relay_state)
                     ├── pysaml2 base64-decode + parse XML
                     ├── pysaml2 verify XML-DSig against IdP cert from metadata
                     ├── pysaml2 enforce NotBefore/NotOnOrAfter (clock_skew=60s)
                     ├── pysaml2 enforce AudienceRestriction == our_entity_id
                     ├── pysaml2 enforce SubjectConfirmation.Recipient == our_acs_url
                     ├── saml_replay.mark_seen(assertion_id, ttl=NotOnOrAfter-now)
                     │     False  → raise SamlReplayError
                     └── return SamlClaims(email, display_name, raw_attrs)
            ├── SamlSignatureError  → 401 signature_invalid    + audit event
            ├── SamlTimingError     → 401 assertion_expired    + audit event
            ├── SamlAudienceError   → 401 audience_mismatch    + audit event
            ├── SamlRecipientError  → 401 recipient_mismatch   + audit event
            ├── SamlReplayError     → 401 assertion_replayed   + audit event
            ├── SamlConfigError     → 503 saml_misconfigured   + audit event
            └── success → existing user-provisioning + token-mint (UNCHANGED)
```

## Public interfaces

### `SamlVerifier.verify_and_extract`

```python
class SamlClaims(BaseModel):
    name_id: str           # SAML NameID, used as the SSO subject identifier
    email: str | None      # mapped from cfg.wanted_attributes["email"] (default "mail")
    display_name: str | None
    raw_attributes: dict[str, list[str]]
    assertion_id: str
    not_on_or_after: datetime

def verify_and_extract(
    self,
    saml_response_b64: str,
    relay_state: str | None,
) -> SamlClaims:
    """Verify signature/timing/audience/recipient, mark replay, return claims.

    Raises:
        SamlSignatureError: signature failed
        SamlTimingError:    NotBefore in future or NotOnOrAfter in past
        SamlAudienceError:  AudienceRestriction missing our entity_id
        SamlRecipientError: SubjectConfirmation.Recipient != our ACS URL
        SamlReplayError:    assertion_id already seen
        SamlConfigError:    internal config issue (caller should 503)
    """
```

### `saml_replay.mark_seen`

```python
async def mark_seen(
    redis: Redis,
    assertion_id: str,
    ttl_seconds: int,
) -> bool:
    """Atomic SET NX + EX. Returns True on first sight (caller proceeds),
    False if the key existed (caller raises SamlReplayError).

    Key shape: 'saml:seen:{assertion_id}'. TTL is bounded to [1, 86400].
    """
```

### Env-var contract

For each provider `<name>`:
- `ADHKAR_SAML_<NAME>_METADATA_URL` — required, IdP metadata endpoint
- `ADHKAR_SAML_<NAME>_ENTITY_ID` — required, our SP entity ID
- `ADHKAR_SAML_<NAME>_ACS_URL` — required, our absolute ACS URL (the IdP-known callback)
- `ADHKAR_SAML_<NAME>_WANTED_ATTRIBUTES` — optional JSON `{"email": "mail", "display_name": "displayName"}`, defaults to standard SAML2 names

`<NAME>` is uppercased; provider lookup at the URL path uses the lowercase form.

## Error handling

All non-success paths emit `audit_and_emit` with:

```python
{
    "action": "saml_verify_failed",
    "entity_type": "user",
    "entity_id": None,
    "diff": {
        "provider": <provider>,
        "reason": <SamlSignatureError|SamlTimingError|...>,
        "source_ip": <request.client.host>,
    },
}
```

Successful verifications continue to use the existing `saml_login` audit event already in `api/v1/saml.py`.

The 503 path (missing verifier) emits a one-shot startup-time audit `saml.metadata_unavailable` plus the per-request 503 — but does NOT spam audit on every request, to avoid log floods if an external scraper hits the ACS URL.

## Testing

### Fixtures
Committed to `backend/tests/auth/fixtures/saml/`:
- `valid_idp_cert.pem` + `valid_idp_key.pem` — test IdP signing keypair
- `attacker_cert.pem` + `attacker_key.pem` — non-IdP keypair used for tampered cases
- `valid_response.xml` — signed by valid IdP, audience matches, fresh window
- `wrong_signer_response.xml` — signed by `attacker_key`
- `expired_response.xml` — `NotOnOrAfter` is `1970-01-01`
- `not_yet_valid_response.xml` — `NotBefore` is year 9999
- `wrong_audience_response.xml` — audience = `https://someone-else.invalid/`
- `wrong_recipient_response.xml` — SubjectConfirmation.Recipient = `https://attacker.invalid/`
- `unsigned_response.xml` — no `<ds:Signature>` element
- `replayed_response.xml` — bit-for-bit identical to `valid_response.xml`
- `valid_idp_metadata.xml` — IdP metadata document referencing `valid_idp_cert.pem`
- `_regenerate.py` — helper that rebuilds every fixture from the committed `.pem` keys using `xmlsec1`. Documented, idempotent, not run by CI.

### Unit tests
- `backend/tests/auth/test_saml_verifier.py`
  - `test_valid_response_returns_claims`
  - `test_wrong_signer_raises_SamlSignatureError`
  - `test_expired_raises_SamlTimingError`
  - `test_not_yet_valid_raises_SamlTimingError`
  - `test_wrong_audience_raises_SamlAudienceError`
  - `test_wrong_recipient_raises_SamlRecipientError`
  - `test_unsigned_raises_SamlSignatureError`
  - `test_replay_second_call_raises_SamlReplayError`
- `backend/tests/auth/test_saml_replay.py` — uses `fakeredis.aioredis`
  - `test_mark_seen_returns_true_first_time`
  - `test_mark_seen_returns_false_on_replay`
  - `test_mark_seen_respects_ttl_expiry`
- `backend/tests/auth/test_saml_loader.py`
  - `test_load_saml_providers_reads_env`
  - `test_build_verifier_returns_none_when_metadata_unreachable`
  - `test_build_verifier_succeeds_with_static_metadata_string`

### Integration test
- `backend/tests/api/v1/test_saml_acs_integration.py`
  - Mounts `app.state.saml_verifiers["test"] = SamlVerifier(...)` built from `valid_idp_metadata.xml` (no network).
  - `test_acs_with_valid_response_issues_token` — POST `valid_response.xml`, expect 200 with access token, audit event `saml_login` written.
  - `test_acs_with_wrong_signer_returns_401` — POST `wrong_signer_response.xml`, expect 401 `signature_invalid`, audit event `saml_verify_failed`.
  - `test_acs_without_verifier_returns_503` — clear the verifier slot, POST any payload, expect 503 `saml_metadata_unavailable`.

### What we DO NOT test in this iteration
- Live SimpleSAMLphp / Keycloak round-trip (deferred — fixtures cover the same surface).
- Multi-provider routing collisions (the loader already enforces unique provider names; tested implicitly).

## Known limitations (documented, accepted)

1. IdP key rotation requires app restart — no background metadata refresh.
2. Encrypted assertions are rejected with `SamlSignatureError` (pysaml2 default behavior when we don't supply a decrypt key).
3. SLO is not implemented; logout is local-only.
4. `xmlsec1` must be installed as a system package on the host; `pysaml2` won't import without it. This is documented in the `README`. CI image gains an `apt-get install xmlsec1` line.

## Rollout

1. Land the implementation behind the existing `verify_saml_response` hook — no flag, no feature toggle. The hook either works (signed assertions accepted) or rejects (unsigned/tampered assertions rejected). The only behavior change for existing deployments is that previously-passing fake assertions now 401.
2. Tag `v1.0.0-rcN.saml-signature-verification`.
3. Memory snapshot updated; deferred-items list shortened.
4. After integration test suite (separate spec) lands, tag `v1.0.0`.
