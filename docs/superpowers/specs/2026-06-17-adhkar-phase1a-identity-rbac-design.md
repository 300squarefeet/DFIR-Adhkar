# Adhkar IR — Phase 1a: Identity, RBAC, MFA, ApiKey, Admin UI (Design Spec)

- Status: Approved (autonomous mode — user instructed "no need to ask, do the best")
- Date: 2026-06-17
- Author: lead engineer
- Scope: Phase 1a only. Phase 1b (Audit + Outbox + Live-feed + presence) follows.

---

## 1. Context

Phase 0 closed at tag `v0.1.0-dev`. Backend has FastAPI factory, Settings, structlog, RFC 7807 errors, OTel bootstrap, DB engine, readiness checks, `/healthz` `/readyz` `/version`, Alembic init with pgvector. Frontend has M3 dense-dark shell, design tokens, 4 primitives (Button/Chip/SeverityBadge/TLPBadge), AppShell with TopAppBar/NavigationDrawer/CommandPalette/HealthPage.

No domain entity, no auth, no RBAC. Phase 1a is the identity foundation that every later phase depends on.

---

## 2. Strategic decisions (locked)

| # | Concern | Decision |
|---|---|---|
| 1 | Auth library | PyJWT 2.x for encode/decode, Authlib for OAuth2/OIDC stubs (Phase 7), argon2-cffi for password hashing |
| 2 | JWT strategy | HS256 with `ADHKAR_SECRET_KEY`; access token 15 min; refresh token 14 d; refresh rotated on each use; Redis denylist for revoked refresh JTI |
| 3 | Token transport | Web: httpOnly + Secure + SameSite=Strict cookie. API/SDK: `Authorization: Bearer <token>` |
| 4 | MFA | TOTP (RFC 6238, 30 s window) + 10 single-use backup codes + org-level enforcement toggle |
| 5 | Password policy | NIST SP 800-63B: min 12 chars, zxcvbn strength ≥ 3, optional HIBP k-anonymity breach check |
| 6 | API keys | Per-permission scoped (subset of user permissions); prefix `adh_`; argon2-hashed at rest; optional expiry (30/90/365 d/never); `last_used_at` tracking |
| 7 | RBAC | 4 default profiles, 14-key fixed permission catalog, profile editor (subset selector) in admin UI |
| 8 | Onboarding | Email invitation flow with signed 24-hour single-use link; force MFA enroll if org requires it |
| 9 | OrgSharing | Minimal: table + link/unlink admin UI only; sharing semantics deferred to Phase 3+ |
| 10 | Multi-tenancy | `OrgScopedRepository[T]` wrapper pattern; current_org from JWT claim |

ADR `0006-auth-stack-pyjwt-authlib.md` will document these.

---

## 3. Data model

All tables follow Phase 0 naming convention (`pk_*`, `fk_*`, `ix_*`, `uq_*`). All entities carry `id` (UUID v4, `pgcrypto.gen_random_uuid()`), `created_at`, `updated_at` (timestamps with timezone). Soft delete via `deleted_at` where noted.

### 3.1 `organizations`

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID | PK | |
| name | text | NOT NULL, unique | display name |
| slug | text | NOT NULL, unique, ~[a-z0-9-]{2,63}~ | url-safe |
| description | text | NULL | |
| require_mfa | boolean | NOT NULL default false | org-level policy |
| locked | boolean | NOT NULL default false | admin-disabled |
| created_at | timestamptz | NOT NULL | |
| updated_at | timestamptz | NOT NULL | |
| deleted_at | timestamptz | NULL | soft delete |

### 3.2 `users`

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID | PK | |
| email | citext | NOT NULL, unique | case-insensitive (citext extension) |
| display_name | text | NOT NULL | |
| password_hash | text | NULL | argon2id, NULL until invite accepted |
| status | text | NOT NULL default 'pending_invite' | enum: pending_invite, active, locked |
| default_org_id | UUID | NULL, FK organizations | last selected org |
| theme | text | NULL | 'dark' | 'light' (mirror frontend setting) |
| created_at | timestamptz | NOT NULL | |
| updated_at | timestamptz | NOT NULL | |
| deleted_at | timestamptz | NULL | |

Plus extension `CREATE EXTENSION IF NOT EXISTS citext`.

### 3.3 `user_org_memberships`

M:N user ↔ organization with role binding.

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| user_id | UUID | FK users, NOT NULL |
| organization_id | UUID | FK organizations, NOT NULL |
| profile_id | UUID | FK profiles, NOT NULL |
| created_at | timestamptz | NOT NULL |
| updated_at | timestamptz | NOT NULL |

Unique constraint `(user_id, organization_id)`.

### 3.4 `profiles`

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID | PK | |
| organization_id | UUID | FK organizations, NOT NULL | profile is org-scoped |
| name | text | NOT NULL | |
| description | text | NULL | |
| permissions | text[] | NOT NULL | subset of `PERMISSION_CATALOG` keys |
| is_default | boolean | NOT NULL default false | seeded default profiles |
| created_at | timestamptz | NOT NULL | |
| updated_at | timestamptz | NOT NULL | |

Unique constraint `(organization_id, name)`.

### 3.5 `api_keys`

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID | PK | |
| user_id | UUID | FK users, NOT NULL | owning user |
| label | text | NOT NULL | user-provided name |
| prefix | text | NOT NULL | first 12 chars (`adh_xxxxxxxx`), for lookup |
| key_hash | text | NOT NULL | argon2id of full key |
| scope_permissions | text[] | NOT NULL | subset of owning user's permissions |
| expires_at | timestamptz | NULL | NULL = never |
| last_used_at | timestamptz | NULL | |
| created_at | timestamptz | NOT NULL | |
| revoked_at | timestamptz | NULL | |

Index on `prefix` (lookup at auth time).

### 3.6 `sessions`

Refresh-token JTI tracking + last-seen for analytics.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID | PK | also the JTI claim |
| user_id | UUID | FK users, NOT NULL | |
| issued_at | timestamptz | NOT NULL | |
| expires_at | timestamptz | NOT NULL | |
| revoked_at | timestamptz | NULL | |
| user_agent | text | NULL | truncated 200 chars |
| ip | inet | NULL | first hop |
| last_seen_at | timestamptz | NOT NULL | updated on refresh |

Index on `(user_id, revoked_at)`.

### 3.7 `mfa_secrets`

One row per user (1:1).

| Column | Type | Constraints | Notes |
|---|---|---|---|
| user_id | UUID | PK, FK users | |
| seed_encrypted | bytea | NOT NULL | TOTP shared secret, AES-GCM encrypted with `ADHKAR_SECRET_KEY` |
| confirmed_at | timestamptz | NULL | NULL = pending verification |
| backup_codes_hash | text[] | NOT NULL | 10 argon2id-hashed single-use codes |
| backup_codes_used | int[] | NOT NULL default '{}' | indices of consumed codes |
| created_at | timestamptz | NOT NULL | |

### 3.8 `org_sharings`

Minimal: just store the link. Phase 3+ adds visibility logic.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID | PK | |
| source_org_id | UUID | FK organizations, NOT NULL | |
| target_org_id | UUID | FK organizations, NOT NULL | |
| kind | text | NOT NULL | enum: 'peer', 'parent' |
| created_by | UUID | FK users, NOT NULL | |
| created_at | timestamptz | NOT NULL | |

Unique `(source_org_id, target_org_id)`. Check `source_org_id != target_org_id`.

### 3.9 Invitation tokens (no table; stateless via `itsdangerous`)

Invite links are signed with `URLSafeTimedSerializer(ADHKAR_SECRET_KEY)` carrying `{user_id, org_id, profile_id, iat}`. Max-age 24 h. Used-tokens tracked by setting user.status from `pending_invite` → `active`; reuse rejected because user already active.

### 3.10 Migration plan

`0002_phase1a_identity.py`: create organizations, users, citext extension, sessions, profiles, user_org_memberships, api_keys, mfa_secrets, org_sharings — all tables in one migration. Seed `org-admin`, `analyst`, `read-only`, `portal-user` default profiles per org via Phase 1a application code (post-org-create hook), not migration.

---

## 4. Auth flow

### 4.1 Login (`POST /v1/auth/login`)

Request: `{email, password, mfa_code?}`. Response on success: `{access_token, token_type: "bearer", expires_in: 900, user: {...}, current_org_id}` plus `Set-Cookie: refresh_token=...; HttpOnly; Secure; SameSite=Strict; Path=/; Max-Age=1209600`.

Logic:
1. Lookup user by email (citext, case-insensitive). 404 → return 401 with generic message (avoid email enumeration).
2. Verify password with `argon2.verify`. Failure → 401 generic.
3. Check user.status: `pending_invite` → 403 `invite-pending`. `locked` → 403 `account-locked`.
4. Lookup user's memberships. None → 403 `no-org`.
5. If user has MFA confirmed:
   - If `mfa_code` absent → respond `401` problem with type `mfa-required`; client re-issues login with code.
   - Verify code via TOTP (cur±1 30-s window) OR consume one backup code. Failure → 401 generic.
6. Pick org: `user.default_org_id` if set and in memberships, else first membership.
7. Issue access JWT + refresh JWT. Insert `sessions` row (JTI = refresh JTI, expires=14d).
8. Return.

Access JWT claims: `{sub: user_id, org_id, perms: [...], jti, iat, exp}`. Perms derived from the profile of the chosen org membership.

### 4.2 Refresh (`POST /v1/auth/refresh`)

Reads refresh JWT from cookie. Verifies signature, claims, expiry. Looks up session by JTI; rejects if revoked. **Rotates**: insert new session row (new JTI), mark old session `revoked_at`. Issue new access + refresh. Return new access token in body + Set-Cookie new refresh.

### 4.3 Logout (`POST /v1/auth/logout`)

Mark current session.revoked_at. Push JTI to Redis denylist with TTL = remaining expiry. Clear cookie.

### 4.4 Me (`GET /v1/auth/me`)

Returns current user + memberships + current_org + permissions.

### 4.5 Password change (`POST /v1/auth/password/change`)

Requires old password. Validates new password with policy (12 chars + zxcvbn 3+ + HIBP). On success, hash + store; **revoke ALL other sessions** for this user (force re-login on other devices).

### 4.6 Password reset

- `POST /v1/auth/password/forgot {email}`: always 204 (no enumeration). If user exists, generate `itsdangerous` token (1-h max-age) and send email.
- `POST /v1/auth/password/reset {token, new_password}`: verify token, validate password, store hash, revoke all sessions.

### 4.7 Invite acceptance

- `GET /v1/auth/invite/{token}`: peek (returns invited email + org name) — public, no auth.
- `POST /v1/auth/invite/accept {token, password, display_name}`: validate token, set password, set display_name, transition user.status → 'active'.

### 4.8 MFA endpoints

- `POST /v1/auth/mfa/enroll`: generate seed (32 random bytes), return base32 + QR provisioning URI (`otpauth://totp/Adhkar:email?secret=...&issuer=Adhkar`). Store encrypted, unconfirmed.
- `POST /v1/auth/mfa/confirm {code}`: verify TOTP code. On success, mark confirmed, generate 10 backup codes (returned ONCE in response), hash them.
- `POST /v1/auth/mfa/disable {password, code}`: require password + current TOTP. Delete row.
- `POST /v1/auth/mfa/backup-codes/regenerate {password, code}`: require password + current TOTP. Generate new 10, return once.

### 4.9 Cookie security

`Set-Cookie` flags: `HttpOnly` (no JS), `Secure` (HTTPS only in prod; dev compose sets `ADHKAR_COOKIE_SECURE=false`), `SameSite=Strict`, `Path=/`. CSRF protection via SameSite=Strict + custom header (`X-Csrf-Token` echoing a cookie-stored CSRF token, double-submit pattern) only on state-changing endpoints when authenticated via cookie. Bearer-token requests are CSRF-safe.

---

## 5. RBAC engine

### 5.1 Permission catalog

`adhkar.auth.permissions.PERMISSION_CATALOG`:

```python
PERMISSION_CATALOG: Final = frozenset({
    "manageOrganization",
    "manageUser",
    "manageProfile",
    "manageApiKey",
    "viewAudit",
    "manageCase",       # Phase 3 wire-up
    "viewCase",
    "manageAlert",      # Phase 4
    "viewAlert",
    "manageObservable", # Phase 2
    "viewObservable",
    "manageTask",
    "viewTask",
    "manageConfig",
})
```

Frozen at module load. Profile editor presents these as checkboxes.

### 5.2 Default profiles (seeded per org-create)

```python
DEFAULT_PROFILES: Final = {
    "org-admin": ALL_PERMISSIONS,
    "analyst": {"manageCase", "viewCase", "manageAlert", "viewAlert",
                "manageObservable", "viewObservable", "manageTask", "viewTask",
                "viewAudit"},
    "read-only": {"viewCase", "viewAlert", "viewObservable", "viewTask"},
    "portal-user": frozenset(),  # placeholder, Phase 9 populates
}
```

When `OrganizationRepository.create()` succeeds, a service hook seeds these 4 profiles in the new org.

### 5.3 Dependency: `require_permission`

```python
def require_permission(name: str):
    async def dep(current_user: Annotated[CurrentUser, Depends(get_current_user)]) -> CurrentUser:
        if name not in current_user.permissions:
            raise HTTPException(403, "missing_permission")
        return current_user
    return dep
```

Usage: `@router.post("/", dependencies=[Depends(require_permission("manageUser"))])`.

### 5.4 `OrgScopedRepository[T]`

```python
class OrgScopedRepository(Generic[T]):
    def __init__(self, session: AsyncSession, current_org_id: UUID):
        self.session = session
        self.current_org_id = current_org_id

    def _scoped(self, stmt: Select) -> Select:
        return stmt.where(self.model.organization_id == self.current_org_id)

    async def list(self) -> list[T]: ...
    async def get(self, id: UUID) -> T | None: ...
    async def create(self, **kwargs) -> T: ...
    async def update(self, id: UUID, **kwargs) -> T: ...
    async def delete(self, id: UUID) -> None: ...
```

Subclasses set `model: type[T]`. `ProfileRepository`, `OrgSharingRepository`, future `ObservableRepository`/`CaseRepository`/etc. extend this.

`current_org_id` resolved by FastAPI dependency `Depends(get_current_org)`:
- For Bearer JWT: read `org_id` claim.
- For cookie session: read access JWT same way (cookie stores refresh; access in body or sent via `Authorization` header in subsequent requests).

Switch org: `POST /v1/auth/switch-org {organization_id}`. Verifies membership, reissues access + refresh tokens with new claim. Required because `org_id` is encoded in the access token (stateless).

### 5.5 Permission resolution at JWT-issue time

When issuing access JWT, look up the user's `UserOrgMembership.profile_id` for the chosen org, fetch `Profile.permissions`, encode into the `perms` claim. Cached for 15 minutes (the access-token lifetime).

API key requests: `Authorization: Bearer adh_...`. Lookup by prefix (first 12 chars), verify full key against argon2 hash, retrieve `scope_permissions`, build synthetic `CurrentUser` with those perms. `last_used_at` updated async.

---

## 6. API endpoints (v1)

All under `/v1`. All require auth except where noted. Responses are RFC 7807 problem+json on error.

### 6.1 Auth

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/v1/auth/login` | public | login (email/password + mfa_code) |
| POST | `/v1/auth/refresh` | refresh cookie | rotate refresh |
| POST | `/v1/auth/logout` | bearer | revoke session |
| GET | `/v1/auth/me` | bearer | current user + memberships |
| POST | `/v1/auth/switch-org` | bearer | issue new tokens with new org_id |
| POST | `/v1/auth/password/change` | bearer | change password |
| POST | `/v1/auth/password/forgot` | public | request reset email |
| POST | `/v1/auth/password/reset` | public | reset with token |
| GET | `/v1/auth/invite/{token}` | public | peek invite |
| POST | `/v1/auth/invite/accept` | public | accept invite |
| POST | `/v1/auth/mfa/enroll` | bearer | start enrollment |
| POST | `/v1/auth/mfa/confirm` | bearer | confirm enrollment |
| POST | `/v1/auth/mfa/disable` | bearer | disable |
| POST | `/v1/auth/mfa/backup-codes/regenerate` | bearer | new backup codes |

### 6.2 Users (admin)

| Method | Path | Permission | Description |
|---|---|---|---|
| GET | `/v1/users` | manageUser | list users in current org |
| POST | `/v1/users/invite` | manageUser | create invite + send email |
| GET | `/v1/users/{id}` | manageUser | detail |
| PATCH | `/v1/users/{id}` | manageUser | update display_name, status, profile_id (in current org membership) |
| DELETE | `/v1/users/{id}` | manageUser | soft delete; revoke all sessions |
| POST | `/v1/users/{id}/reset-mfa` | manageUser | admin clears user's MFA |
| POST | `/v1/users/{id}/lock` | manageUser | set status=locked |
| POST | `/v1/users/{id}/unlock` | manageUser | set status=active |

### 6.3 Organizations

| Method | Path | Permission | Description |
|---|---|---|---|
| GET | `/v1/organizations` | bearer (any) | list orgs user is member of |
<!-- POST removed: Phase 1a creates orgs via CLI bootstrap only. API endpoint deferred to a future ADR (multi-org self-serve / platform-admin role). -->
| GET | `/v1/organizations/{id}` | bearer (member) | detail |
| PATCH | `/v1/organizations/{id}` | manageOrganization | update name, description, require_mfa, locked |
| GET | `/v1/organizations/{id}/sharing` | manageOrganization | list sharing links |
| POST | `/v1/organizations/{id}/sharing` | manageOrganization | create link `{target_org_id, kind}` |
| DELETE | `/v1/organizations/{id}/sharing/{sharing_id}` | manageOrganization | delete |

### 6.4 Profiles

| Method | Path | Permission | Description |
|---|---|---|---|
| GET | `/v1/profiles` | manageProfile | list profiles in current org |
| POST | `/v1/profiles` | manageProfile | create `{name, description, permissions[]}` |
| GET | `/v1/profiles/{id}` | manageProfile | detail |
| PATCH | `/v1/profiles/{id}` | manageProfile | update; cannot edit `org-admin` default permissions |
| DELETE | `/v1/profiles/{id}` | manageProfile | reject if any membership uses it; cannot delete defaults |

### 6.5 API keys

| Method | Path | Permission | Description |
|---|---|---|---|
| GET | `/v1/me/api-keys` | bearer | list own keys |
| POST | `/v1/me/api-keys` | bearer | create `{label, scope_permissions[], expires_at?}`; response shows full key ONCE |
| DELETE | `/v1/me/api-keys/{id}` | bearer | revoke own key |
| GET | `/v1/users/{id}/api-keys` | manageApiKey | admin view |
| DELETE | `/v1/users/{id}/api-keys/{kid}` | manageApiKey | admin revoke |

---

## 7. Frontend admin UI

### 7.1 New routes

```
/login                  — LoginPage
/login/mfa              — MfaChallengePage
/invite/:token          — AcceptInvitePage
/password/forgot        — ForgotPasswordPage
/password/reset/:token  — ResetPasswordPage
/me/profile             — UserProfilePage
/me/mfa                 — MfaEnrollPage
/me/api-keys            — ApiKeysPage
/admin/users            — UsersAdminPage
/admin/organizations    — OrganizationsAdminPage
/admin/organizations/:id/sharing  — OrgSharingPage
/admin/profiles         — ProfilesAdminPage
```

### 7.2 AuthContext + useAuth

`frontend/src/lib/auth.tsx`:
- `AuthProvider` wraps Providers. State: `user | null`, `currentOrg | null`, `permissions: Set<string>`.
- On mount: try `GET /v1/auth/me` (existing access in cookie). On 401: stay logged out.
- On login response: store in state.
- `useAuth()` hook returns state + login/logout/switchOrg methods.
- Router guard: if route is not in `PUBLIC_ROUTES`, redirect to `/login`.

### 7.3 Permission gates

`<RequirePermission name="manageUser">` component:
```tsx
const { permissions } = useAuth();
if (!permissions.has(name)) return <NotAllowed/>;
return <>{children}</>;
```

Used to wrap admin nav items and pages.

### 7.4 Updated NavigationDrawer

Replace disabled placeholder for "Admin" with submenu:
- Users (`/admin/users`)
- Organizations (`/admin/organizations`)
- Profiles (`/admin/profiles`)

Visible only if any of `manageUser`/`manageOrganization`/`manageProfile` in permissions. Each submenu item gated by its specific permission.

### 7.5 TopAppBar

Replace `@user` stub with UserMenu component:
- Avatar (initial of display_name)
- Display name + current org name
- Items: Profile, MFA, API keys, Switch organization (lists user's memberships), Logout

### 7.6 LoginPage

Form: email + password. Submit → API. On `mfa-required` problem, route to `/login/mfa` and re-submit with code. On success, navigate to `/` (HealthPage stays default in Phase 1a; Phase 3+ replaces with case list).

### 7.7 MfaEnrollPage

Three steps:
1. Click "Enroll" → API returns QR + secret. Show QR via `qrcode.react` and the secret as fallback.
2. Enter 6-digit code → confirm.
3. Display 10 backup codes; user copy + acknowledge.

### 7.8 Admin > Users

TanStack Table with columns: email, display_name, profile (in current org), status, last_login, actions. Action menu per row: Edit, Reset MFA, Lock/Unlock, Delete. Top-right: "Invite user" button → modal with email + profile selector + sends invite via API.

### 7.9 Admin > Organizations

List orgs user is member of. Detail page: name/desc/require_mfa toggle/locked toggle. Tab "Linked organizations" lists sharings; add via modal (search target org by slug); delete inline.

### 7.10 Admin > Profiles

List profiles in current org. Edit modal: name, description, checkbox grid of 14 permissions. `org-admin` profile shows checkboxes pre-checked and disabled (cannot edit). Delete blocked for default profiles + profiles in use.

---

## 8. Testing strategy

### 8.1 Backend

Add to existing `backend/tests/`:

- `unit/test_auth_password.py` — argon2 hash/verify; password policy boundaries; HIBP mock
- `unit/test_auth_jwt.py` — encode/decode + claims + expiry + tampering
- `unit/test_auth_tokens.py` — access + refresh rotation; denylist
- `unit/test_auth_mfa.py` — TOTP generation + verification; backup code consume
- `unit/test_auth_invite.py` — token sign/verify, single-use enforcement
- `unit/test_permissions.py` — catalog frozen; default profiles correctness
- `unit/test_org_scope.py` — repository wrapper filter behavior
- `integration/test_auth_flow.py` — full login → MFA → /me → refresh → logout cycle against testcontainers
- `integration/test_admin_users.py` — invite → accept → user activated → admin list/lock/delete
- `integration/test_rbac.py` — analyst cannot manageOrg, org-admin can; permission boundary tests

Coverage threshold raised to 75% per spec §8.4.

### 8.2 Frontend

- `pages/LoginPage.test.tsx` — happy path + mfa-required flow
- `pages/MfaEnrollPage.test.tsx` — render QR, confirm, backup codes
- `pages/AcceptInvitePage.test.tsx`
- `pages/admin/UsersAdminPage.test.tsx` — list + invite modal + action menu
- `pages/admin/ProfilesAdminPage.test.tsx` — checkbox grid behavior
- `lib/auth.test.tsx` — context + hook + guard
- `lib/permissions.test.tsx` — RequirePermission component

Coverage threshold raised to 65%.

### 8.3 No-shortcut policy

- All authz checks tested both ways (allowed + denied).
- Multi-tenancy isolation tested explicitly: user in org A cannot see profile in org B.
- Password reset token cannot be reused.
- Refresh rotation cannot be replayed.

---

## 9. Definition of Done

Phase 1a is done when ALL hold:

### 9.1 Migrations + seeds
- [ ] `0002_phase1a_identity.py` applies clean; `downgrade base` reverses cleanly.
- [ ] `citext` and `pgcrypto` extensions enabled (pgcrypto already done Phase 0; verify).
- [ ] Bootstrap CLI seeds first org + first user + default profiles: `uv run python -m adhkar.cli bootstrap --org-name "Acme" --admin-email admin@example.com --admin-password '…'`.

### 9.2 Backend
- [ ] All 30+ endpoints in §6 implemented with proper authz dependency, RFC 7807 errors.
- [ ] `OrgScopedRepository[T]` abstract + 3 concrete impls (ProfileRepository, UserMembershipRepository, OrgSharingRepository).
- [ ] `argon2-cffi`, `pyjwt`, `authlib`, `pyotp`, `qrcode[pil]`, `zxcvbn-python`, `httpx` (for HIBP), `itsdangerous`, `pydantic[email]` added to deps.
- [ ] JWT issuance + verification works end-to-end.
- [ ] Email sending via MailHog (dev) verified in integration test by polling MailHog HTTP API.
- [ ] All integration tests in §8.1 pass.

### 9.3 Frontend
- [ ] Login → MFA → HealthPage flow works in browser against running compose.
- [ ] Admin pages render and CRUD operations work.
- [ ] AuthContext persists user across page reloads.
- [ ] Switch-org reissues tokens and refetches data.

### 9.4 Security tests
- [ ] No SQL string concatenation anywhere (parameterized queries).
- [ ] CSRF protection on cookie-authenticated POST/PUT/PATCH/DELETE.
- [ ] Bcrypt → argon2 transition NOT NEEDED (we start on argon2).
- [ ] Refresh tokens are httpOnly + Secure + SameSite=Strict.
- [ ] No leaking of internal exceptions in 500 responses.

### 9.5 Quality gates
- [ ] backend-quality CI green: ruff, mypy strict, pytest coverage ≥ 75%.
- [ ] frontend-quality CI green: lint, typecheck, vitest coverage ≥ 65%, build.
- [ ] integration CI green: testcontainers spin pg+redis+minio+mailhog; full auth round-trip + admin flow.

### 9.6 Docs
- [ ] ADR `0006-auth-stack-pyjwt-authlib.md` written.
- [ ] `docs/runbook.md` updated: bootstrap CLI, MailHog UI link.
- [ ] `docs/architecture.md` updated: identity layer added to system view.
- [ ] `docs/api.md`: link to Swagger groups for auth/users/profiles/api-keys.

### 9.7 Demo
- [ ] `docker compose up` → bootstrap CLI → open browser → log in → admin invites second user → user accepts invite → user logs in → admin changes profile to read-only → user re-logs in and confirms reduced permissions.

---

## 10. Handoff peek: Phase 1b

Phase 1b adds:
- `audit_logs` table append-only (actor, action, entity_type, entity_id, diff JSONB, request_id, ip, ts).
- `outbox_events` table; transactional outbox pattern: writing a domain mutation and emitting an event are atomic.
- Worker (Phase 1b ships a minimal asyncio worker; full Celery/Arq is Phase 2 decision) reads `outbox_events`, publishes to Redis pub/sub channel `adhkar.events.<org_id>`.
- WebSocket endpoint `GET /v1/live` (authenticated): client subscribes to events; backend forwards Redis messages.
- Frontend: `useLiveFeed()` hook + presence indicator in TopAppBar; live activity feed panel on right rail (collapsible).
- All Phase 1a mutations get audit + outbox wiring retroactively.

This is the foundation for Phase 2+ real-time UX.

---

## 11. Out of scope (explicit)

- SSO / OAuth2 / OIDC / SAML — Phase 7
- LDAP / AD — Phase 7
- WebAuthn / passkeys — Phase 7/10
- Per-resource fine-grained ACL beyond permission keys — not planned
- Password aging / rotation requirements — explicit choice to skip (NIST 800-63B discourages)
- Brute-force lockout (counts + temporary lock) — Phase 10 hardening
- Rate limiting per endpoint — Phase 10 hardening (basic FastAPI-Limiter applied generously now)
- Multi-language UI (i18n) — not Phase 1a
- User profile picture upload — Phase 3 (when attachments arrive)

---

## 12. Risk register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| HIBP API down on signup blocks user | Med | Low | Soft-fail: log warning, allow password (HIBP is bonus, not gate) |
| pgcrypto.gen_random_uuid() collision | Negligible | Negligible | UUID v4 collision is cryptographically improbable |
| MFA seed leak from compromised SECRET_KEY | Low | Critical | Document key rotation procedure (manual decrypt + re-encrypt) in runbook |
| Refresh-token theft | Low | High | httpOnly + Secure + SameSite=Strict + rotation + denylist |
| Email enumeration via login/forgot timing | Med | Low | Constant-time bcrypt-style comparison; uniform response codes |
| Profile editor user accidentally drops own `manageProfile` | Low | Medium | Confirmation modal + block dropping last `manageProfile` holder |

---

## 13. References

- NIST SP 800-63B Digital Identity Guidelines
- RFC 6238 TOTP
- RFC 7519 JWT
- OWASP ASVS 4.0.3 L2
- HaveIBeenPwned Pwned Passwords API v3 (k-anonymity)
- Authlib docs (Phase 7 prep)

End of spec. Next: implementation plan via `superpowers:writing-plans`.
