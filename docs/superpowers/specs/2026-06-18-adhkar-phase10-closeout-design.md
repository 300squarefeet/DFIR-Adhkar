# Phase 10 Closeout — Design

**Status:** Approved 2026-06-18
**Phase:** 10 (Hardening, final)
**Goal:** Land 5 hardening items and tag `v1.0.0` final.

## Problem

`phase10/hardening` carries 125+ RC tags (RC149 → RC274). The #1 security blocker (SAML signature verification) closed in RC263–RC274. Five outstanding items still gate a clean `v1.0.0`:

1. README does not mention the `xmlsec1` system package requirement; a fresh `git clone` + `uv sync` hits a confusing `pysaml2` ImportError.
2. Audit rows currently record `request.client.host`. Behind a reverse proxy that is the LB's IP, not the real client. SOC analysts triaging brute-force lose attribution.
3. Every rejected SAML assertion at `/v1/auth/saml/{provider}/acs` emits both an `AuditLog` row AND an `OutboxEvent`. A scraper POSTing junk floods the Redis pub/sub bus.
4. RC261 (the CaseDetailPage "Your activity" badge consuming `/v1/cases/{id}/contributors/me` (RC260)) was killed mid-flight during the autonomous loop and never landed. The backend endpoint has no consumer.
5. End-to-end integration coverage is one file (`test_readyz_integration.py`) plus two SAML failure-mode tests. The 113-RC autonomous-loop surface has zero round-trip verification against real Postgres + Redis.

After these five items land, the repo can be tagged `v1.0.0`.

## Goal

After closeout:

- `xmlsec1` documented in `README.md`
- Audit rows record the real client IP behind any standard reverse proxy
- Rejected SAML assertions write AuditLog only (no OutboxEvent)
- CaseDetailPage shows the "Your activity" badge
- Critical-path integration tests boot Postgres + Redis + MinIO via testcontainers and prove the SAML happy-path, case CRUD, alert promote-to-case, observable attach, and notification dispatch end-to-end
- `v1.0.0` tag exists on the closing commit

## Non-goals (deferred to v1.0.x or v1.1)

- Broad integration coverage of every Phase 0–9 endpoint surface
- Configurable trust-boundary for `X-Forwarded-For` (we trust the header; document the deploy assumption)
- Encrypted SAML assertions, SLO, IdP-initiated SSO, background metadata refresh (all carried forward from the SAML spec's known limitations)
- Frontend consumers for the other autonomous-loop backend filters that have no UI (RC222 days/entity, RC227 q, RC246 since, RC253 attempts_gte, several CSV-export filters) — Phase 11
- TipTap rich-text upgrade, `@dnd-kit` true drag-and-drop — Phase 11

## Architectural decisions (locked)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| `v1.0.0` lands at the end of this closeout | Yes | User decision: this is the GA milestone |
| Integration suite size | Critical-path (~7 tests) | User decision: balance between SAML-only (too thin) and broad coverage (gates GA too long) |
| Integration fixture scope | Session-scoped shared docker stack | One Postgres/Redis/MinIO triple per pytest session; reused across all integration tests for speed |
| Trust X-Forwarded-For unconditionally | Yes | Operators deploy behind their own LB; configurability is YAGNI |
| OutboxEvent suppression mechanism | New `emit_outbox: bool = True` kwarg on `audit_and_emit` | Smaller diff than splitting into two helpers; explicit at every call site |
| Tag convention | Sequence of `v1.0.0-rcN.*` RCs, then a lightweight `v1.0.0` tag on the final commit | Matches existing project pattern |
| CI gating | Integration suite stays gated on docker availability (`@pytest.mark.integration`) | Existing convention from `test_readyz_integration.py` |

## File structure

| File | Status | Responsibility |
|------|--------|----------------|
| `README.md` | **modify** | Add "Prerequisites" subsection naming `xmlsec1` and `libxmlsec1-dev` as required system packages; reference `backend/Dockerfile` as the canonical install. ~5 lines of markdown. |
| `backend/adhkar/core/source_ip.py` | **create** | Single public function `source_ip(request: Request) -> str \| None`. Parse X-Forwarded-For (left-most non-private/non-loopback), fall back X-Real-IP, fall back `request.client.host`. ~30 LOC. |
| `backend/adhkar/audit.py` | **modify** | Extend `audit_and_emit(...)` signature with `emit_outbox: bool = True` keyword. When False, write `AuditLog` only — no `OutboxEvent`. ~5 LOC change. |
| `backend/adhkar/core/ratelimit.py` | **modify** | Replace inline `request.client.host` with `source_ip(request)`. |
| `backend/adhkar/api/v1/auth.py` | **modify** | Replace 4 inline `request.client.host` call sites with `source_ip(request)`. |
| `backend/adhkar/api/v1/saml.py` | **modify** | (a) Replace `_audit_failed` body's IP capture with `source_ip(request)`. (b) Pass `emit_outbox=False` in the `audit_and_emit` call inside `_audit_failed`. |
| `frontend/src/pages/CaseDetailPage.tsx` | **modify** | Add `MyContrib` interface + state, fetch `/v1/cases/${caseId}/contributors/me` on mount, render inline badge near the page header. Hidden when sum === 0. Same shape as the killed RC261 spec. |
| `backend/tests/unit/test_source_ip.py` | **create** | 4 tests: header missing → client.host; valid XFF → left-most; XFF with private IPs → first non-private; malformed XFF → fallback. |
| `backend/tests/unit/test_audit_emit_flag.py` | **create** | 2 tests: default emits Outbox; `emit_outbox=False` writes AuditLog only. Uses an in-memory sqlite session like other audit unit tests. |
| `backend/tests/integration/conftest.py` | **create** | Session-scoped fixture `pg_redis_minio_stack` boots three testcontainers, applies Alembic migrations, yields `{pg_url, redis_url, minio_url, s3_bucket}`. Reused across all integration tests in the session. Skip-loud (not fail-loud) when docker unavailable. |
| `backend/tests/integration/test_saml_acs_happy_path.py` | **create** | POST a valid signed assertion to `/v1/auth/saml/test/acs`, assert 200 + valid access_token + User row exists. Deferred from Task 10. |
| `backend/tests/integration/test_cases_crud.py` | **create** | Create → patch (severity + tags) → soft-delete; verify AuditLog row at each step. |
| `backend/tests/integration/test_alert_promote.py` | **create** | Create alert → POST promote → case row exists + `alert.case_id` set + audit. |
| `backend/tests/integration/test_observables_attach.py` | **create** | Create observable → attach to case → GET similarity-counts shows it → detach → similarity-counts updated. |
| `backend/tests/integration/test_notifications_dispatch.py` | **create** | Create notification endpoint + rule → emit triggering audit event → wait for `NotificationDelivery` row with `status=succeeded`. |
| `/Users/salma/.claude/projects/-Users-salma-Documents-Research-TheBee/memory/project-adhkar-ir.md` | **modify** | Append the v1.0.0 closeout snapshot. |

## Data flow / behavior

### Item 1 — README

No runtime change. A `## Prerequisites` heading lands above the existing setup instructions:

> SAML signature verification requires the `xmlsec1` system package. Install before `uv sync`:
>
> - macOS: `brew install libxmlsec1`
> - Debian/Ubuntu: `sudo apt-get install -y xmlsec1 libxmlsec1-dev`
>
> The `backend/Dockerfile` and CI workflows install these automatically; only fresh local clones need to do it manually.

### Item 2 — source_ip helper

```python
def source_ip(request: Request) -> str | None:
    xff = request.headers.get("x-forwarded-for")
    if xff:
        # Left-most non-private IP wins
        for raw in xff.split(","):
            ip = raw.strip()
            if ip and not _is_private_or_loopback(ip):
                return ip
    xri = request.headers.get("x-real-ip")
    if xri:
        return xri.strip()
    return request.client.host if request.client else None
```

`_is_private_or_loopback` uses `ipaddress.ip_address(...).is_private` + `.is_loopback`. Malformed strings raise `ValueError` which is caught and treated as private (skipped).

### Item 3 — audit_and_emit flag

```python
async def audit_and_emit(
    db: AsyncSession,
    *,
    actor_user_id: UUID | None,
    organization_id: UUID | None,
    action: str,
    entity_type: str,
    entity_id: UUID | None,
    diff: dict[str, Any] | None = None,
    request_id: str | None = None,
    ip: str | None = None,
    event_type: str | None = None,
    payload: dict[str, Any] | None = None,
    emit_outbox: bool = True,
) -> tuple[AuditLog, OutboxEvent | None]:
    ...
    if emit_outbox:
        outbox = OutboxEvent(...)
        db.add(outbox)
        return audit, outbox
    return audit, None
```

Callers that ignored the second tuple element keep working. The single new call site (`_audit_failed`) passes `emit_outbox=False` and discards the second element.

### Item 4 — Your-activity badge

Append the existing handler patterns on `CaseDetailPage.tsx`:

```typescript
interface MyContrib {
  user_id: string;
  comment_count: number;
  task_log_count: number;
  audit_count: number;
}

const [myContrib, setMyContrib] = useState<MyContrib | null>(null);

useEffect(() => {
  apiCall<MyContrib>(`/v1/cases/${caseId}/contributors/me`)
    .then(setMyContrib)
    .catch(() => undefined);
}, [apiCall, caseId]);
```

Render directly under the case `<h1>`:

```tsx
{myContrib && (myContrib.comment_count + myContrib.task_log_count + myContrib.audit_count > 0) && (
  <aside className="mt-1 inline-flex items-center gap-2 rounded-full bg-md-sys-color-surface-container px-3 py-0.5 text-xs">
    <span className="font-medium">Your activity:</span>
    <span>{myContrib.comment_count} comments · {myContrib.task_log_count} task updates · {myContrib.audit_count} audits</span>
  </aside>
)}
```

### Item 5 — Integration suite

Shared fixture lifecycle:

```
session start
  └── pg_redis_minio_stack (session-scoped, autouse=False)
        ├── PostgresContainer("postgres:16-alpine").start()
        ├── RedisContainer("redis:7-alpine").start()
        ├── MinioContainer("minio/minio:latest").start()
        ├── alembic upgrade head (against pg_url)
        ├── yield {pg_url, redis_url, minio_url, s3_bucket}
        └── containers.stop()
```

Each test file imports `pg_redis_minio_stack` as a fixture, then builds an `AsyncSession` against `pg_url` and an `httpx.AsyncClient` over an ASGI transport with `ADHKAR_DATABASE_URL` + `ADHKAR_REDIS_URL` env vars pointed at the containers.

Test isolation: each test runs in its own SQLAlchemy savepoint that's rolled back at the end (no truncate, no cross-test leakage).

The five test files cover:

| File | Verifies |
|------|----------|
| `test_saml_acs_happy_path.py` | Signed SAML assertion → 200 + access_token + User row + audit |
| `test_cases_crud.py` | Case create + PATCH + soft-delete → 3 AuditLog rows |
| `test_alert_promote.py` | Alert promote → case + linked alert + 1 audit row |
| `test_observables_attach.py` | Observable attach + similarity-counts roundtrip + detach |
| `test_notifications_dispatch.py` | Endpoint + rule + triggering event → `NotificationDelivery(status=succeeded)` |

## Error handling

| Surface | Failure mode | Handler |
|---------|--------------|---------|
| `source_ip` | Malformed XFF entry | Treat as private (skip), continue to next candidate |
| `source_ip` | No request.client | Return `None` |
| `audit_and_emit(emit_outbox=False)` | Existing callers unmodified | Return tuple's second slot becomes `None`; callers that did `audit, outbox = ...` see `outbox is None` |
| Testcontainers boot | Docker not available | `pytest.skip("docker not available")` — matches `test_readyz_integration.py` |
| Testcontainers boot | Alembic migration fails | Fail the test session — that's a real bug |
| CaseDetailPage badge | `/contributors/me` 404 / 500 | Silently set `myContrib = null` → badge hidden |

## Rollout / RC sequence

| RC | Item | Branch state |
|----|------|--------------|
| RC275 | README xmlsec1 note | `phase10/hardening` |
| RC276 | `source_ip` helper + call-site sweep | + `+src + tests` |
| RC277 | `audit_and_emit(emit_outbox=...)` + ACS opt-out | + `+audit + saml.py` |
| RC278 | CaseDetail your-activity badge (RC261 retried) | + `+CaseDetailPage.tsx` |
| RC279 | Testcontainers integration suite (~7 tests + conftest) | + `+conftest + 5 test files` |
| RC280 | Plan doc commit + memory snapshot | `docs/` + memory |
| `v1.0.0` | Lightweight tag at RC280's commit | GA |

## Testing strategy

- **Items 1–3, 5 (small RCs)**: existing project test patterns. Unit tests for `source_ip`; unit test for `audit_and_emit(emit_outbox=False)`; smoke test that the full pytest suite stays green. Frontend item RC278: `pnpm typecheck && pnpm lint && pnpm test --run`.
- **Item 5 (integration suite)**: introduces the docker fixture. Test isolation via savepoint rollback (not truncate). Skip-on-no-docker matches existing convention. Optional: a single end-to-end fixture-boot smoke test that just asserts the conftest fixture yields valid URLs, so a docker misconfig fails fast before per-test runs.
- **`v1.0.0` gate**: full unit suite + integration suite + ruff + mypy all green; smoke routes; memory snapshot updated.

## Known limitations (documented, accepted)

1. We trust `X-Forwarded-For` unconditionally. Operators must deploy behind a sanitizing reverse proxy (any IP we record can be spoofed if requests reach the app directly). Documented in README.
2. Integration suite covers 7 critical paths; full Phase 0–9 round-trip coverage is Phase 10.x or 11.
3. Testcontainers boot adds ~30s to a clean CI run when docker is available. Acceptable.
