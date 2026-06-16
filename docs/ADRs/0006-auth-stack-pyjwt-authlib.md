# 0006. Auth stack — PyJWT + Authlib + argon2-cffi

- Status: Accepted
- Date: 2026-06-17
- Deciders: project lead (autonomous mode)
- Tags: auth, security, architecture

## Context and Problem Statement

Phase 1a builds the identity layer (login, MFA, password reset, API keys, RBAC). We need primitives for: JWT encode/decode, password hashing, TOTP, signed-link tokens, and a path for future OAuth2/OIDC/SAML (Phase 7).

Three realistic options exist: (a) hand-pick narrow libraries and wire them ourselves; (b) use a turnkey solution like `fastapi-users`; (c) DIY everything from primitives.

## Decision Drivers

- RBAC + multi-tenancy + per-permission API key scopes are non-standard — most turnkey libraries don't model them cleanly
- Future Phase 7 needs OAuth2/OIDC/SAML connectors
- Minimize attack surface (narrow, audited libraries)
- Avoid magic — every auth path is greppable
- Test-friendly (small interfaces)

## Considered Options

1. **PyJWT + Authlib + argon2-cffi + pyotp + itsdangerous** (chosen)
2. `fastapi-users` turnkey — opinionated user model, hard to extend for multi-org/profile/RBAC
3. `python-jose` + DIY everything — no Phase 7 prep, more work

## Decision Outcome

Chosen: narrow primitive stack. Specifically:

| Concern | Library | Why |
|---|---|---|
| JWT encode/decode | `pyjwt` | Industry default, narrow API, no magic |
| OAuth2/OIDC/SAML stubs | `authlib` | Phase 7 prep; only used in Phase 1a for nothing yet but already on disk |
| Password hashing | `argon2-cffi` | OWASP-recommended; tunable cost; resistant to GPU/ASIC |
| TOTP | `pyotp` | RFC 6238 compliant; minimal |
| Signed link tokens (invite/reset) | `itsdangerous` | URLSafeTimedSerializer; Flask-pedigree, stable |
| QR generation | `qrcode[pil]` | for MFA enrollment provisioning URI |
| Password strength | `zxcvbn-python` | NIST 800-63B-aligned entropy check |
| Breach check | `httpx` (existing) → HIBP k-anonymity API | privacy-preserving; soft-fail |
| Email validation | `pydantic[email]` | already pulled in by pydantic |

### JWT specifics

- Algorithm: `HS256` with `ADHKAR_SECRET_KEY` (rotation strategy: redeploy with new key invalidates all tokens — acceptable in self-hosted; multi-key kid rotation deferred to Phase 10 hardening).
- Access token lifetime: **15 minutes**.
- Refresh token lifetime: **14 days**, rotated on each use.
- Refresh storage: `sessions` table tracks issued JTIs; rotated tokens mark predecessor `revoked_at`. Redis denylist tracks logout-revoked JTIs with TTL = remaining expiry.
- Claims: `sub` (user_id), `org_id` (current chosen org), `perms` (list of permission keys), `jti`, `iat`, `exp`.

### Transport

- Web (browser): refresh token in `httpOnly; Secure; SameSite=Strict; Path=/` cookie. Access token returned in response body, expected to be cached in JavaScript memory and sent as `Authorization: Bearer <access>`.
- API / SDK: `Authorization: Bearer <token>` only. No cookies.
- CSRF protection: SameSite=Strict on the refresh cookie + double-submit `X-CSRF-Token` for cookie-authenticated state-changing endpoints.

### Password hashing parameters

`argon2id` with: `time_cost=2`, `memory_cost=64 MB`, `parallelism=2`, `hash_len=32`. Tunable via env vars for tests (lower cost) and high-security deployments.

## Positive Consequences

- Each piece is independently testable.
- No vendor lock-in.
- Phase 7 SSO connectors slot into Authlib cleanly.
- Greppable: `pyjwt` usage shows the exact JWT generation/verification paths.

## Negative Consequences

- More boilerplate than a turnkey solution.
- We own the auth bugs (good and bad). Mitigated by:
  - Comprehensive integration tests (positive + negative authz)
  - OWASP ASVS L2 checklist applied to every endpoint
  - Bandit + Semgrep in CI (Phase 0 already wired)

## Links

- ADR 0002 (license) — auth code stays under Apache-2.0 in core
- Spec §4–§5 of `2026-06-17-adhkar-phase1a-identity-rbac-design.md`
