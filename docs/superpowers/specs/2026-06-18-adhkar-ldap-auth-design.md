# LDAP / Active Directory Auth Provider — Design

**Status:** Approved 2026-06-18
**Phase:** 11 (post-v1.0.0 feature parity)
**Goal:** Close the #1 enterprise-readiness gap vs TheHive 5 by adding LDAP/Active Directory authentication with group→profile auto-provisioning.

## Problem

TheHive 5 ships first-class LDAP and Active Directory authentication: service-account bind, user search, memberOf-driven group→profile mapping, and an admin UI for managing providers and mappings. Adhkar IR `v1.0.0` ships SAML 2.0, OIDC, and local credentials with TOTP MFA — but no LDAP. The Adhkar↔TheHive parity audit (2026-06-18) flagged LDAP as the most-frequently-requested enterprise enablement gap: many on-prem financial / government deployments still rely on AD as their canonical identity store and have no modern IdP.

After this lands, Adhkar can:

- Authenticate users against one or more LDAP / AD servers without a separate IdP.
- Auto-provision User rows + org memberships from AD group membership on first login.
- Sync membership diffs on every login (groups added/removed in AD reflect in Adhkar immediately).
- Preserve memberships an org admin attached manually — LDAP sync only touches `source='ldap'` rows.
- Edit provider config + group→profile mappings live via the admin UI (no app restart).

## Goal

After this design lands:

- A new `LdapProvider` + `LdapGroupMapping` schema exists.
- `POST /v1/auth/login` falls back to LDAP after a local-password mismatch (transparent fallback — no new endpoint).
- Auto-provision is JIT on every successful login: User upsert + membership diff against `source='ldap'`.
- TLS (`ldaps://`) is enforced by default; per-provider `allow_insecure` flag exists for dev only and emits an audit warning on every use.
- Admin UI at `/admin/ldap` lists providers, lets admins create/edit/delete, runs a Test-connection probe, and manages per-provider group→profile mappings.
- A 7-test integration suite (testcontainers `bitnami/openldap:2.6` + seeded LDIF) proves the end-to-end happy + sad paths.

## Non-goals (deferred to v1.2+)

- LDAP-only password change / reset (LDAP users keep `password_hash=NULL`; password ops go through AD).
- Scheduled group-sync job (we sync on login only — no background poll).
- Nested-group resolution beyond direct `memberOf` (AD-style recursive group expansion via LDAP_MATCHING_RULE_IN_CHAIN).
- LDAP as an alert source / observable enrichment.
- Replicating the existing `OrgSharing` flow over LDAP-sourced users.
- Per-tenant overrides of provider config (config is org-global).

## Architectural decisions (locked)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Library | `ldap3` (pure Python, BSD) | No system deps (vs `python-ldap`'s `libldap2-dev`); aligns with the same "fewer prereqs" line we drew during the `xmlsec1` README note. |
| Bind mode | Service-account search-then-bind | Required for `memberOf` group lookup. AD-direct UPN bind doesn't expose groups without a second search. |
| Provisioning | TheHive-style auto-provision via group→profile mapping | User decision (Q1). Zero-touch enterprise onboarding. |
| MFA interplay | Skip Adhkar TOTP MFA after LDAP bind | User decision (Q2). Trust the directory. Consistent with SAML/OIDC. |
| Login UX | Transparent fallback (local → LDAP) at `/v1/auth/login` | User decision (Q3). No new endpoint, no provider dropdown. |
| Config storage | DB-backed (`ldap_providers` + `ldap_group_mappings`) + admin UI | User decision (Q4). Live edit, audit trail, full parity. |
| Group-sync failure | Fail-closed (no mapping match AND no manual membership → 403) | Honors the "auto-provision via groups" contract; admin escape hatch via manual membership stays open. |
| Membership tracking | Add `user_org_memberships.source: str` (`manual` / `ldap`) | Lets sync touch only LDAP-sourced rows; manual rows survive group removal. |
| TLS | `ldaps://` default; `allow_insecure: bool` per provider with audit warning on every use | Secure default; explicit + audited override for dev. |
| Circuit breaker | Redis-keyed `ldap:fail:{provider_id}`, 50 fails / 60s → 5 min cooldown | Caps damage from a misbehaving server without operator intervention. |
| Bind password at rest | Fernet (key derived from `ADHKAR_SECRET_KEY`) via existing `auth/crypto.py` helper | Reuses the same encryption surface as other secret material. |
| Anonymous-bind guard | Reject `password == ""` before dialing | ldap3 default accepts empty pw as anonymous-bind success — must guard explicitly. |
| Estimated RC | 7-9 RCs on a new `phase11/ldap-auth` branch | Bounded scope; each RC path-scoped per the existing project convention. |

## File structure

| File | Status | Responsibility |
|------|--------|----------------|
| `backend/adhkar/db/models/ldap_provider.py` | **create** | `LdapProvider` + `LdapGroupMapping` ORM models. |
| `backend/alembic/versions/00XX_ldap_auth.py` | **create** | Migration: `ldap_providers`, `ldap_group_mappings`, `user_org_memberships.source` column. |
| `backend/adhkar/auth/ldap_errors.py` | **create** | Typed exception hierarchy (`LdapError`, `LdapConnectionError`, `LdapInvalidCredentials`, etc.). |
| `backend/adhkar/auth/ldap_client.py` | **create** | Thin `ldap3` wrapper: `bind_and_search`, `user_bind`. ~80 LOC. No DB. |
| `backend/adhkar/auth/ldap_provider.py` | **create** | `LdapProviderConfig` frozen dataclass loaded from a row; decrypts `bind_password_enc` on construction. ~50 LOC. |
| `backend/adhkar/auth/ldap_service.py` | **create** | `LdapAuthService`: orchestrates provider iteration, group resolution, user/membership upsert. ~150 LOC. |
| `backend/adhkar/auth/crypto.py` | **modify** | Add `encrypt_bind_password` / `decrypt_bind_password` helpers if not already shaped. |
| `backend/adhkar/api/v1/auth.py` | **modify** | Extend `POST /v1/auth/login` to fall back to `LdapAuthService.try_bind` on local mismatch / unknown user. |
| `backend/adhkar/api/v1/admin_ldap.py` | **create** | CRUD + Test-connection + mappings endpoints. ~250 LOC. |
| `backend/adhkar/db/models/membership.py` | **modify** | Add `source: Mapped[str]` column, default `'manual'`. |
| `frontend/src/pages/AdminLdapPage.tsx` | **create** | Provider list, edit drawer, mappings table, Test button. ~400 LOC. |
| `frontend/src/app/AppShell.tsx` | **modify** | Add LDAP nav entry under Admin section, gated on `manageConfig`. |
| `backend/tests/unit/test_ldap_client.py` | **create** | 5 tests: mocked `ldap3.Connection`. |
| `backend/tests/unit/test_ldap_service.py` | **create** | 10 tests: provider iteration, resolution, upsert, circuit breaker. |
| `backend/tests/unit/test_ldap_provider_config.py` | **create** | 2 tests: Fernet round-trip, URI validation. |
| `backend/tests/unit/test_ldap_errors.py` | **create** | 3 tests: exception → status code matrix, password redaction. |
| `backend/tests/integration/test_ldap_login.py` | **create** | 5 tests against `bitnami/openldap:2.6`. |
| `backend/tests/integration/test_admin_ldap_endpoints.py` | **create** | 2 tests: CRUD + Test-connection. |
| `backend/tests/integration/fixtures/seed.ldif` | **create** | 3 users, 2 groups. |
| `frontend/src/pages/AdminLdapPage.test.tsx` | **create** | 6 vitest cases (msw). |
| `README.md` | **modify** | LDAP prerequisite note (none — pure Python). Mention the feature in the feature list. |
| `/Users/salma/.claude/projects/-Users-salma-Documents-Research-TheBee/memory/project-adhkar-ir.md` | **modify** | Append v1.1 LDAP snapshot. |

## Data model

```python
# backend/adhkar/db/models/ldap_provider.py

class LdapProvider(Base, IdMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "ldap_providers"

    name: Mapped[str] = mapped_column(String(64), unique=True)
    server_uris: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    bind_dn: Mapped[str] = mapped_column(String(500))
    bind_password_enc: Mapped[str] = mapped_column(String(500))
    base_dn: Mapped[str] = mapped_column(String(500))
    user_search_filter: Mapped[str] = mapped_column(String(300))
    user_id_attr: Mapped[str] = mapped_column(String(64), default="sAMAccountName")
    user_email_attr: Mapped[str] = mapped_column(String(64), default="mail")
    user_display_name_attr: Mapped[str] = mapped_column(String(64), default="displayName")
    group_membership_attr: Mapped[str] = mapped_column(String(64), default="memberOf")
    tls_required: Mapped[bool] = mapped_column(Boolean, default=True)
    allow_insecure: Mapped[bool] = mapped_column(Boolean, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    priority: Mapped[int] = mapped_column(Integer, default=100)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=5)


class LdapGroupMapping(Base, IdMixin, TimestampMixin):
    __tablename__ = "ldap_group_mappings"
    __table_args__ = (UniqueConstraint("ldap_provider_id", "group_dn", "organization_id"),)

    ldap_provider_id: Mapped[UUID] = mapped_column(
        PgUUID, ForeignKey("ldap_providers.id", ondelete="CASCADE")
    )
    group_dn: Mapped[str] = mapped_column(String(500))
    organization_id: Mapped[UUID] = mapped_column(PgUUID, ForeignKey("organizations.id"))
    profile_id: Mapped[UUID] = mapped_column(PgUUID, ForeignKey("profiles.id"))
```

Membership source-tracking:
```sql
ALTER TABLE user_org_memberships
  ADD COLUMN source VARCHAR(20) NOT NULL DEFAULT 'manual';
CREATE INDEX ix_memberships_source ON user_org_memberships(source);
```

## Components

### LdapClient (`auth/ldap_client.py`)
Thin wrapper over `ldap3.Connection`. No DB knowledge. Methods:
- `bind_and_search(bind_dn, bind_password, base_dn, search_filter, attributes) -> list[dict]`
- `user_bind(user_dn, password) -> bool` (False on `invalidCredentials`)

Raises `LdapConnectionError` on socket/TLS failure. Always `try/finally: connection.unbind()`. Empty-password guard at entry. Never includes password in exception args.

### LdapProviderConfig (`auth/ldap_provider.py`)
Frozen dataclass loaded from a `LdapProvider` row. Decrypts `bind_password_enc` via `auth/crypto.py` on construction. Validates `server_uris` shape.

### LdapAuthService (`auth/ldap_service.py`)
Public entrypoint: `try_bind(db, email, password) -> BindResult | None`.

```python
@dataclass
class BindResult:
    provider_id: UUID
    user_dn: str
    email: str
    display_name: str
    matched_group_dns: list[str]
    resolved_memberships: list[tuple[UUID, UUID]]   # [(org_id, profile_id), ...]
```

Algorithm:
1. Load enabled providers ordered by `priority ASC`.
2. For each provider: check circuit breaker → service-bind → user search → user-bind → fetch `memberOf` → resolve mappings (skip soft-deleted orgs) → return `BindResult`.
3. Skip provider on `LdapConnectionError` / `LdapServiceBindError`, advance to next.
4. If every provider fails with connection errors → raise `LdapAllProvidersFailed`.
5. If a provider returns 0-hit search OR `user_bind` returns False → raise `LdapInvalidCredentials` immediately (don't try other providers — credential is wrong, not a server issue).

`upsert_user_and_memberships(db, result) -> User`:
1. `INSERT ... ON CONFLICT (email) DO UPDATE` on `users` — display_name refreshed from LDAP.
2. Load existing LDAP-source memberships for this user.
3. Compute `to_add = resolved - existing_ldap`, `to_remove = existing_ldap - resolved`.
4. Apply diff. Emit `ldap_user_provisioned` (first-time) or `ldap_membership_sync` (returning).
5. Single transaction. Audit write inside the same TX — failure rolls back.

Fail-closed check: if `resolved_memberships` is empty AND user has zero memberships with `source='manual'` → raise `LdapNoAuthorizedGroup`.

### Circuit breaker
Redis key `ldap:fail:{provider_id}` (counter, `INCR` + `EXPIRE 60s`). On `INCR > 50` → set `ldap:open:{provider_id}` TTL 300s. `try_bind` checks `EXISTS ldap:open:{id}` first; if set, skip with audit `ldap_circuit_open`.

### Admin endpoints (`api/v1/admin_ldap.py`)

| Method | Path | Permission |
|---|---|---|
| GET | `/v1/admin/ldap-providers` | `manageConfig` |
| POST | `/v1/admin/ldap-providers` | `manageConfig` |
| GET | `/v1/admin/ldap-providers/{id}` | `manageConfig` |
| PATCH | `/v1/admin/ldap-providers/{id}` | `manageConfig` |
| DELETE | `/v1/admin/ldap-providers/{id}` (soft) | `manageConfig` |
| POST | `/v1/admin/ldap-providers/{id}/test-connection` | `manageConfig` |
| GET | `/v1/admin/ldap-providers/{id}/mappings` | `manageConfig` |
| POST | `/v1/admin/ldap-providers/{id}/mappings` | `manageConfig` |
| DELETE | `/v1/admin/ldap-providers/{id}/mappings/{mapping_id}` | `manageConfig` |

Test-connection: tries service-bind + a no-op search, returns `{ok: bool, server_uri_used: str, error: str | None, duration_ms: int}`. Always audited.

### Frontend (`AdminLdapPage.tsx`)
- Provider list table: name, server URIs (truncated), enabled toggle, # mappings, Test button.
- Edit drawer: name, server URIs (multi-input), bind DN, bind password (write-only — never read back), base DN, search filter, attribute mappings (collapsible advanced section), TLS flags, priority, timeout.
- Mappings panel per provider: group_dn input + org select + profile select + Add; existing mappings table with delete buttons.
- Test button → loading spinner → success/error toast.
- Soft-delete via existing confirm-dialog primitive.

## Data flow

### Local login (unchanged path)
`POST /v1/auth/login` → existing local verify → issue tokens. LDAP never touched.

### First-time LDAP login
`POST /v1/auth/login {email, password}` → SELECT users WHERE email=? → not found (or `password_hash IS NULL`, or password mismatch on `password_hash IS NULL`-having user) → `LdapAuthService.try_bind`:
1. Iterate providers in priority order.
2. Service-bind → search `(user_search_filter applied with email/uid)`.
3. User-bind with supplied password.
4. Fetch `memberOf`.
5. Resolve `(org_id, profile_id)` tuples via `LdapGroupMapping` JOIN.
6. Open TX. Insert User (`password_hash=NULL`, `status='active'`, `default_org_id=first matched org`). Insert memberships with `source='ldap'`. Emit `ldap_user_provisioned` audit. Commit.
7. Issue tokens.

### Returning LDAP user
Same up to step 5. Step 6 differs: load existing `source='ldap'` memberships, compute diff, apply, emit `ldap_membership_sync` if diff non-empty. Manual memberships untouched.

### Failure paths

| Scenario | Behavior | Status code |
|----------|----------|-------------|
| Local pw mismatch + LDAP disabled / no providers | 401 `invalid_credentials` | 401 |
| Local pw mismatch + every LDAP provider returns invalidCredentials | 401 `invalid_credentials` | 401 |
| Every LDAP provider service-bind / network failure | 503 `ldap_unavailable` + audit `ldap_connection_failed` per provider | 503 |
| LDAP bind ok, user search 0 hits | 401 `invalid_credentials` (anti-enumeration; identical message to wrong-pw) | 401 |
| LDAP bind ok, user-bind invalidCredentials | 401 `invalid_credentials` | 401 |
| LDAP bind ok, group lookup zero matched mappings, no manual membership | 403 `ldap_no_authorized_group` + audit | 403 |
| LDAP bind ok, group sukses, `audit_and_emit` raises | TX rollback → 500 (no token issued if audit fails) | 500 |

## Error handling

| Surface | Failure mode | Handler |
|---------|--------------|---------|
| `LdapClient.bind_and_search` | TLS/socket failure | Raise `LdapConnectionError`; service skips to next provider. |
| `LdapClient` | Empty password | Raise `LdapInvalidCredentials` before dialing. |
| `LdapClient` | Exception during connection | `try/finally: unbind()` to release socket. |
| `LdapClient` exception strings | — | Never include password; guarded by `test_password_not_leaked_in_exception`. |
| `LdapAuthService.try_bind` | All providers connection-failed | Raise `LdapAllProvidersFailed` → endpoint returns 503 `ldap_unavailable`. |
| `LdapAuthService.try_bind` | Search 0 hits / wrong password | Raise `LdapInvalidCredentials` → endpoint returns 401 (anti-enumeration: identical message vs unknown email). |
| `LdapAuthService.resolve_memberships` | Soft-deleted org referenced | Skip mapping; mention in `ldap_membership_sync` diff `skipped`. |
| `LdapAuthService.upsert` | `audit_and_emit` raises | TX rollback; no token issued; 500. |
| Circuit breaker | Provider over threshold | `try_bind` skips with audit `ldap_circuit_open`. |
| `allow_insecure=True` provider used | — | Audit `ldap_insecure_used` on every login; `/readyz` flags degraded when recent entries are found. |
| Admin PATCH password rotation | — | Encrypted before insert; no log emission of the plain value. |
| Bind during provider with `enabled=False` | — | Provider skipped silently (not an error). |

## Audit events added

- `ldap_user_provisioned` — first-time User row from LDAP
- `ldap_membership_sync` — diff `{added: [...], removed: [...]}` on LDAP-sourced memberships
- `ldap_connection_failed` — service-bind error per provider (`emit_outbox=False` — anti-flood)
- `ldap_no_authorized_group` — bind ok but no group match and no manual membership
- `ldap_circuit_open` — circuit breaker engaged
- `ldap_insecure_used` — emitted on every login that traversed a provider with `allow_insecure=True`; `/readyz` reads counts of this action over the last 5 min to surface a `degraded` flag
- `ldap_provider_created` / `_updated` / `_deleted` — admin CRUD
- `ldap_test_connection` — admin Test button

## Testing strategy

### Unit (~20 tests, no docker)
- `test_ldap_client.py`: mock `ldap3.Connection` via `MockSyncStrategy`. Bind success, search returns entries, `LDAPSocketOpenError` → `LdapConnectionError`, `invalidCredentials=True` → user_bind False, empty password guard.
- `test_ldap_service.py`: mock `LdapClient`. Priority order, first-success, skip-and-continue on connection failure, `LdapAllProvidersFailed` on all-fail, resolution filters soft-deleted orgs, fail-closed when no mappings + no manual memberships, manual memberships preserved, circuit breaker engages at 51 fails.
- `test_ldap_provider_config.py`: Fernet encrypt/decrypt round-trip; URI validator rejects malformed.
- `test_ldap_errors.py`: status code matrix, password redaction in exception str.

### Integration (~7 tests, testcontainers)
`bitnami/openldap:2.6` seeded with LDIF:
- 1 admin user in `SOC Admins` group
- 2 analyst users in `SOC Analysts` group
- 1 user in `Marketing` group (unmapped — fail-closed test target)

Tests in `test_ldap_login.py`:
1. First login auto-provisions User + 2 memberships (`source='ldap'`).
2. Wrong password returns 401, no User row.
3. Unmapped-group user returns 403 `ldap_no_authorized_group`, no User row.
4. Returning user with changed groups: memberships diff'd (add + remove) on second login.
5. Manual membership preserved across LDAP sync.

Tests in `test_admin_ldap_endpoints.py`:
6. Admin POST provider + GET shows it; Test-connection returns ok=True.
7. Test-connection with wrong svc creds returns ok=False + audit log entry exists.

### Frontend (~6 vitest, msw)
`AdminLdapPage.test.tsx`: list renders, create form submits, Test toast on success, mapping add/delete, soft-delete confirm, 400 error toast.

### Coverage targets
- Backend unit coverage on `auth/ldap_*` ≥ 90%.
- Integration suite gated on docker availability (existing `@pytest.mark.integration` pattern).

## Rollout / RC sequence

| RC | Item | Branch state |
|----|------|--------------|
| RC1 | Models + Alembic migration (ldap_providers, ldap_group_mappings, user_org_memberships.source) | `phase11/ldap-auth` |
| RC2 | `auth/ldap_errors.py` + `auth/ldap_client.py` + unit tests | + |
| RC3 | `auth/ldap_service.py` + unit tests (priority, resolution, upsert, circuit breaker) | + |
| RC4 | Extend `POST /v1/auth/login` to fall back to LDAP + unit + endpoint tests | + |
| RC5 | `api/v1/admin_ldap.py` CRUD + Test-connection + permission tests | + |
| RC6 | `AdminLdapPage.tsx` + vitest cases | + |
| RC7 | Integration test suite (testcontainers + 7 tests) | + |
| RC8 | Memory snapshot + spec/plan doc commits | + |
| `v1.1.0` | Lightweight tag on RC8 commit | post-GA |

## Known limitations (documented, accepted)

1. Group sync is JIT (on login only). Users dropped from an LDAP group keep access until they next log in. Acceptable: existing JWT TTL is 15 min; impact is bounded.
2. No nested-group expansion. Direct `memberOf` only. AD recursive groups require explicit flat mapping.
3. Bind password rotation works (PATCH), but in-flight connections during rotation may complete with the old password. Acceptable: connections are short-lived per login.
4. Test-connection runs in the request thread (no async). Slow LDAP server can stall the admin endpoint up to `timeout_seconds`. Acceptable: admin-only, low-frequency.
5. We do NOT support LDAP referrals. Multi-tier AD forests must point Adhkar at the canonical DC.
