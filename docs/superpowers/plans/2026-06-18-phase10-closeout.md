# Phase 10 Closeout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land the final 5 hardening items (xmlsec1 README, X-Forwarded-For helper sweep, OutboxEvent opt-out on rejected SAML, CaseDetailPage your-activity badge, and a ~7-test critical-path testcontainers suite) and tag `v1.0.0`.

**Architecture:** Each sub-item is a self-contained RC tagged on `phase10/hardening`. Path-scoped commits avoid the index-sweep collision pattern documented in `[[feedback-path-scoped-commits]]`. The integration suite reuses (by hoisting to conftest.py) the existing `services` fixture from `test_readyz_integration.py` so a single session-scoped Postgres + Redis + MinIO stack serves all integration tests.

**Tech Stack:** Python 3.12 + FastAPI, `pysaml2`, `testcontainers[postgres,redis,minio]`, `pytest-asyncio` strict mode, `fakeredis` (already in deps), Alembic, React 18 + TanStack Router for the frontend item.

**Spec reference:** `docs/superpowers/specs/2026-06-18-adhkar-phase10-closeout-design.md` (commit `ba75562`).

---

## Plan review notes

Fixes applied during a post-write review pass (2026-06-18, xhigh effort):

1. **Task 2 helper signature** uses `starlette.requests.Request` directly instead of a `Protocol` stub. The unit tests' duck-typed `_StubRequest` still works at runtime; the project's mypy is scoped to `adhkar/` (not `tests/`) so no per-test ignores are needed.
2. **Task 4 audit-emit unit test** uses `unittest.mock.MagicMock` + `AsyncMock` instead of SQLite. Reason: `AuditLog` declares `INET + JSONB + PgUUID`; `OutboxEvent` declares `JSONB + PgUUID`. SQLite cannot honor those dialect types at `create_all`, so a real-session test would fail at fixture setup.
3. **Task 4 Step 3a** added: confirm no existing caller destructures `audit, outbox = await audit_and_emit(...)` and dereferences `outbox.id`. Verified during plan review (all 18 call sites in the codebase discard the return or only use the AuditLog); the new `tuple[AuditLog, OutboxEvent | None]` return type is safe.
4. **Tasks 7–10 bearer-token bootstrap** dropped the fictional `X-Adhkar-Org` request header. The `org_id` is carried in the JWT — `issue_tokens(org_id=org.id, ...)` encodes it, `get_current_user` decodes it, `require_current_org` reads `user.org_id`. The integration tests only need the standard `Authorization: Bearer <token>` header.
5. **Tasks 7–10 bootstrap helpers** had `await engine.dispose()` written AFTER `return ...` (unreachable). Wrapped the `async with Session()` in a `try/finally` so the engine is always disposed.
6. **Tasks 6–10 async fixtures** used `@pytest.fixture` on `async def app_*(...)` functions. With the project's `asyncio_mode = "strict"`, async fixtures must use `@pytest_asyncio.fixture` (and `import pytest_asyncio`). Same plan bug surfaced multiple times during the SAML plan; carried the fix forward here as the default.

## Pre-flight

**Branch:** stay on `phase10/hardening`. HEAD is currently `ba75562` (spec doc).

**Path-scoped commits.** Always use `git commit -s -m "..." -- <exact paths>`. Never `git add` then bare `git commit`.

**Tag naming.** Each task ends with `git tag v1.0.0-rcN.<slug>`. The last task (Task 11) creates the lightweight `v1.0.0` tag in addition to its RC.

**Validation cadence.** Every backend task ends with `cd backend && uv run ruff check --fix . && uv run ruff format . && uv run mypy adhkar && uv run pytest tests/unit/ -q` plus the OpenAPI route-coverage smoke test. Integration-test tasks additionally run `uv run pytest tests/integration/ -q -m integration` if docker is available, otherwise document the skip.

**`xmlsec1` requirement.** Tasks 4 and beyond may run pysaml2 code; ensure `xmlsec1 libxmlsec1-dev` is installed (Task 1 of the SAML plan added it to CI; locally `brew install libxmlsec1` on macOS).

---

## Task 1: README xmlsec1 prerequisites note

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Read the current README**

```bash
cd /Users/salma/Documents/Research/adhkar-ir && head -40 README.md
```
Identify where the existing setup / dependency text lives. We will insert a `## Prerequisites` section immediately above the first `## Setup` (or equivalent) heading. If no setup heading exists, insert near the top after the project description.

- [ ] **Step 2: Add the Prerequisites section**

Insert this block at the right place:

```markdown
## Prerequisites

SAML signature verification requires the `xmlsec1` binary and `libxmlsec1` headers. Install them before running `uv sync`:

- **macOS:** `brew install libxmlsec1`
- **Debian / Ubuntu:** `sudo apt-get install -y xmlsec1 libxmlsec1-dev`

`backend/Dockerfile` and `.github/workflows/ci.yml` install these automatically; only fresh local clones need to do it manually.
```

- [ ] **Step 3: Smoke**

```bash
cd /Users/salma/Documents/Research/adhkar-ir && grep -c "xmlsec1" README.md
```
Expected: ≥ 1 match.

- [ ] **Step 4: Commit + tag (path-scoped)**

```bash
cd /Users/salma/Documents/Research/adhkar-ir
git commit -s -m "$(cat <<'EOF'
docs(readme): document xmlsec1 system-package prerequisite

A fresh git clone + uv sync without xmlsec1 fails with an unhelpful
pysaml2 ImportError. The Prerequisites section gives the macOS and
Debian install commands; the Dockerfile and CI already install
xmlsec1 automatically.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)" -- README.md
git tag v1.0.0-rc275.readme-xmlsec1
```

---

## Task 2: `source_ip` helper + unit tests

**Files:**
- Create: `backend/adhkar/core/source_ip.py`
- Create: `backend/tests/unit/test_source_ip.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/unit/test_source_ip.py`:

```python
"""source_ip extracts the real client IP from a FastAPI Request."""

from __future__ import annotations

from typing import Any

import pytest
from starlette.datastructures import Headers


class _StubClient:
    def __init__(self, host: str) -> None:
        self.host = host


class _StubRequest:
    """Minimal duck-type stand-in for fastapi.Request."""

    def __init__(self, headers: dict[str, str], client_host: str | None) -> None:
        self.headers = Headers(headers)
        self.client = _StubClient(client_host) if client_host else None


def _r(headers: dict[str, str] | None = None, client_host: str | None = "127.0.0.1") -> Any:
    return _StubRequest(headers or {}, client_host)


@pytest.fixture
def source_ip_fn():
    from adhkar.core.source_ip import source_ip

    return source_ip


def test_returns_left_most_xff_when_present(source_ip_fn) -> None:
    req = _r({"x-forwarded-for": "203.0.113.42, 10.0.0.1, 10.0.0.2"})
    assert source_ip_fn(req) == "203.0.113.42"


def test_skips_private_xff_entries(source_ip_fn) -> None:
    req = _r({"x-forwarded-for": "10.0.0.1, 192.168.1.5, 203.0.113.42"})
    assert source_ip_fn(req) == "203.0.113.42"


def test_falls_back_to_x_real_ip_when_no_xff(source_ip_fn) -> None:
    req = _r({"x-real-ip": "198.51.100.7"})
    assert source_ip_fn(req) == "198.51.100.7"


def test_falls_back_to_client_host_when_no_headers(source_ip_fn) -> None:
    req = _r({}, client_host="192.0.2.1")
    assert source_ip_fn(req) == "192.0.2.1"


def test_returns_none_when_no_signal(source_ip_fn) -> None:
    req = _r({}, client_host=None)
    assert source_ip_fn(req) is None


def test_treats_malformed_xff_entries_as_private_and_skips(source_ip_fn) -> None:
    req = _r({"x-forwarded-for": "not-an-ip, 203.0.113.42"})
    assert source_ip_fn(req) == "203.0.113.42"


def test_loopback_xff_entries_are_skipped(source_ip_fn) -> None:
    req = _r({"x-forwarded-for": "127.0.0.1, 203.0.113.42"})
    assert source_ip_fn(req) == "203.0.113.42"
```

- [ ] **Step 2: Run tests to verify failure**

```bash
cd /Users/salma/Documents/Research/adhkar-ir/backend && uv run pytest tests/unit/test_source_ip.py -q
```
Expected: `ModuleNotFoundError: No module named 'adhkar.core.source_ip'`.

- [ ] **Step 3: Implement the helper**

Create `backend/adhkar/core/source_ip.py`:

```python
"""Resolve the real client IP for a request.

Order:
  1. left-most non-private, non-loopback entry in X-Forwarded-For
  2. X-Real-IP header
  3. request.client.host
  4. None

The caller MUST sit behind a sanitizing reverse proxy in production —
we trust forwarded headers unconditionally."""

from __future__ import annotations

import ipaddress

from starlette.requests import Request


def _is_private_or_loopback(ip: str) -> bool:
    try:
        parsed = ipaddress.ip_address(ip.strip())
    except ValueError:
        # Malformed → treat as private so the next entry gets considered.
        return True
    return parsed.is_private or parsed.is_loopback or parsed.is_link_local


def source_ip(request: Request) -> str | None:
    xff = request.headers.get("x-forwarded-for")
    if xff:
        for raw in xff.split(","):
            candidate = raw.strip()
            if candidate and not _is_private_or_loopback(candidate):
                return candidate
    xri = request.headers.get("x-real-ip")
    if xri:
        return xri.strip()
    if request.client is not None:
        return request.client.host
    return None
```

The test stub at Step 1 duck-types as `Request`; mypy will flag the call site but tests pass it through `# type: ignore[arg-type]` if the implementer hits a mypy error there. Acceptable — the unit-test stub layout matches Starlette's `Request` interface (headers + client).

- [ ] **Step 4: Run tests to verify they pass + lint + typecheck**

```bash
cd /Users/salma/Documents/Research/adhkar-ir/backend && \
  uv run pytest tests/unit/test_source_ip.py -q && \
  uv run ruff check adhkar/core/source_ip.py tests/unit/test_source_ip.py && \
  uv run ruff format adhkar/core/source_ip.py tests/unit/test_source_ip.py && \
  uv run mypy adhkar/core/source_ip.py
```
Expected: `7 passed`, ruff + mypy clean.

- [ ] **Step 5: Commit + tag (path-scoped)**

```bash
cd /Users/salma/Documents/Research/adhkar-ir
git commit -s -m "$(cat <<'EOF'
feat(core): source_ip helper resolves real client IP

Walks X-Forwarded-For (left-most non-private/non-loopback entry),
then X-Real-IP, then request.client.host, then None. Treats
malformed XFF entries as private so the next candidate gets a
chance. Project assumption: deploy behind a sanitizing reverse
proxy.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)" -- backend/adhkar/core/source_ip.py backend/tests/unit/test_source_ip.py
git tag v1.0.0-rc276.source-ip-helper
```

---

## Task 3: Replace `request.client.host` call sites with `source_ip`

**Files:**
- Modify: `backend/adhkar/core/ratelimit.py`
- Modify: `backend/adhkar/api/v1/auth.py`
- Modify: `backend/adhkar/api/v1/saml.py`

There are 5 call sites:

| File | Line | Current |
|------|------|---------|
| `backend/adhkar/core/ratelimit.py` | 67 | `client = request.client.host if request.client else "unknown"` |
| `backend/adhkar/api/v1/auth.py` | 115 | `ip=request.client.host if request.client else None` |
| `backend/adhkar/api/v1/auth.py` | 146 | `ip=request.client.host if request.client else None` |
| `backend/adhkar/api/v1/auth.py` | 202 | `ip=request.client.host if request.client else None` |
| `backend/adhkar/api/v1/saml.py` | 165 | `"source_ip": (request.client.host if request.client else None)` |

- [ ] **Step 1: Modify `ratelimit.py`**

Open `backend/adhkar/core/ratelimit.py`. At the top of the file, ADD the import:

```python
from adhkar.core.source_ip import source_ip
```

Find the line:
```python
        client = request.client.host if request.client else "unknown"
```
Replace with:
```python
        client = source_ip(request) or "unknown"
```

- [ ] **Step 2: Modify `api/v1/auth.py`**

Open `backend/adhkar/api/v1/auth.py`. At the top of the file, ADD the import (or add to an existing `from adhkar.core...` import line):

```python
from adhkar.core.source_ip import source_ip
```

Find all three lines that read:
```python
        ip=request.client.host if request.client else None,
```
Replace each with:
```python
        ip=source_ip(request),
```

- [ ] **Step 3: Modify `api/v1/saml.py`**

Open `backend/adhkar/api/v1/saml.py`. At the top of the file, ADD the import:

```python
from adhkar.core.source_ip import source_ip
```

Find the line inside `_audit_failed`:
```python
                "source_ip": (request.client.host if request.client else None),
```
Replace with:
```python
                "source_ip": source_ip(request),
```

- [ ] **Step 4: Verify no `request.client.host` references remain**

```bash
cd /Users/salma/Documents/Research/adhkar-ir && \
  grep -rn "request.client.host" backend/adhkar/ 2>/dev/null | grep -v __pycache__
```
Expected: **zero matches**. (If you see any, replace them with `source_ip(request)` too.)

- [ ] **Step 5: Run full unit suite + lint + typecheck**

```bash
cd /Users/salma/Documents/Research/adhkar-ir/backend && \
  uv run ruff check adhkar/core/ratelimit.py adhkar/api/v1/auth.py adhkar/api/v1/saml.py && \
  uv run ruff format adhkar/core/ratelimit.py adhkar/api/v1/auth.py adhkar/api/v1/saml.py && \
  uv run mypy adhkar/core/ratelimit.py adhkar/api/v1/auth.py adhkar/api/v1/saml.py && \
  uv run pytest tests/unit/ -q
```
Expected: ruff + mypy clean, all unit tests pass (~204).

- [ ] **Step 6: Commit + tag (path-scoped)**

```bash
cd /Users/salma/Documents/Research/adhkar-ir
git commit -s -m "$(cat <<'EOF'
refactor(core): use source_ip helper at every request-IP capture site

ratelimit middleware + 3 auth handlers + the SAML audit-failed
helper now go through adhkar.core.source_ip.source_ip instead of
inline request.client.host. Behind a reverse proxy, audit rows and
rate-limit keys now see the real client IP via X-Forwarded-For /
X-Real-IP.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)" -- backend/adhkar/core/ratelimit.py backend/adhkar/api/v1/auth.py backend/adhkar/api/v1/saml.py
git tag v1.0.0-rc276a.source-ip-callsite-sweep
```

---

## Task 4: `audit_and_emit(emit_outbox=...)` + SAML ACS opt-out

**Files:**
- Modify: `backend/adhkar/audit.py`
- Modify: `backend/adhkar/api/v1/saml.py`
- Create: `backend/tests/unit/test_audit_emit_flag.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/test_audit_emit_flag.py`:

```python
"""audit_and_emit(emit_outbox=False) writes AuditLog without OutboxEvent.

Uses a MagicMock AsyncSession (no real database) because AuditLog and
OutboxEvent use Postgres-specific dialect types (INET, JSONB, PgUUID)
that can't round-trip through SQLite. We assert by inspecting what
db.add() received."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from adhkar.audit import audit_and_emit
from adhkar.db.models import AuditLog, OutboxEvent


def _mock_session() -> MagicMock:
    sess = MagicMock()
    sess.add = MagicMock()
    sess.flush = AsyncMock()
    return sess


@pytest.mark.asyncio
async def test_default_writes_audit_and_outbox() -> None:
    db = _mock_session()
    audit, outbox = await audit_and_emit(
        db,
        actor_user_id=None,
        organization_id=None,
        action="touched",
        entity_type="case",
        entity_id=uuid4(),
        diff={"k": "v"},
    )
    assert isinstance(audit, AuditLog)
    assert isinstance(outbox, OutboxEvent)
    added_types = [type(call.args[0]).__name__ for call in db.add.call_args_list]
    assert "AuditLog" in added_types
    assert "OutboxEvent" in added_types
    assert db.flush.await_count == 1


@pytest.mark.asyncio
async def test_emit_outbox_false_skips_outbox() -> None:
    db = _mock_session()
    audit, outbox = await audit_and_emit(
        db,
        actor_user_id=None,
        organization_id=None,
        action="rejected",
        entity_type="user",
        entity_id=None,
        diff={"why": "tampered"},
        emit_outbox=False,
    )
    assert isinstance(audit, AuditLog)
    assert outbox is None
    added_types = [type(call.args[0]).__name__ for call in db.add.call_args_list]
    assert "AuditLog" in added_types
    assert "OutboxEvent" not in added_types
    assert db.flush.await_count == 1
```

- [ ] **Step 2: Run to verify failure**

```bash
cd /Users/salma/Documents/Research/adhkar-ir/backend && uv run pytest tests/unit/test_audit_emit_flag.py -q
```
Expected: failure — `TypeError: audit_and_emit() got an unexpected keyword argument 'emit_outbox'`.

- [ ] **Step 3: Extend `audit_and_emit`**

Open `backend/adhkar/audit.py`. Update the function signature and return type:

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
```

Replace the existing outbox emit block at the bottom of the function:
```python
    outbox = OutboxEvent(
        organization_id=organization_id,
        event_type=event_type or f"{entity_type}.{action}",
        payload=event_payload,
    )
    db.add(outbox)
    await db.flush()
    return audit, outbox
```
with:
```python
    if emit_outbox:
        outbox: OutboxEvent | None = OutboxEvent(
            organization_id=organization_id,
            event_type=event_type or f"{entity_type}.{action}",
            payload=event_payload,
        )
        db.add(outbox)
    else:
        outbox = None
    await db.flush()
    return audit, outbox
```

The `event_payload` variable is computed earlier in the function — keep that computation even when `emit_outbox=False` (it's cheap; saves a branch).

- [ ] **Step 3a: Confirm no existing caller destructures the return tuple**

The signature change widens the return type from `tuple[AuditLog, OutboxEvent]` to `tuple[AuditLog, OutboxEvent | None]`. Any caller doing `audit, outbox = await audit_and_emit(...)` followed by `outbox.id` etc. would break. Verify:

```bash
cd /Users/salma/Documents/Research/adhkar-ir && \
  grep -rn "audit, outbox\|, outbox = await audit_and_emit" backend/adhkar/ 2>/dev/null | grep -v __pycache__
```
Expected: **zero matches** outside `audit.py` itself. (Confirmed during plan review: all 18 call sites in the codebase discard the return entirely.) If you find any, narrow that site's type guard before proceeding.

- [ ] **Step 4: Update `_audit_failed` in SAML ACS to opt out of outbox**

Open `backend/adhkar/api/v1/saml.py`. Find the `_audit_failed` helper and the `audit_and_emit(...)` call inside it. Add `emit_outbox=False` as a keyword:

```python
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
                "source_ip": source_ip(request),
            },
            emit_outbox=False,
        )
```

- [ ] **Step 5: Run unit suite + lint + typecheck**

```bash
cd /Users/salma/Documents/Research/adhkar-ir/backend && \
  uv run pytest tests/unit/ -q && \
  uv run ruff check adhkar/audit.py adhkar/api/v1/saml.py tests/unit/test_audit_emit_flag.py && \
  uv run ruff format adhkar/audit.py adhkar/api/v1/saml.py tests/unit/test_audit_emit_flag.py && \
  uv run mypy adhkar/audit.py adhkar/api/v1/saml.py
```
Expected: 2 new tests pass, ruff + mypy clean, full unit suite green.

- [ ] **Step 6: Commit + tag (path-scoped)**

```bash
cd /Users/salma/Documents/Research/adhkar-ir
git commit -s -m "$(cat <<'EOF'
feat(audit): emit_outbox flag to suppress live-feed event on failures

audit_and_emit gains a keyword emit_outbox: bool = True. When False
the AuditLog row still gets written but the OutboxEvent is skipped.
SAML ACS _audit_failed uses emit_outbox=False so a scraper POSTing
junk to /v1/auth/saml/{provider}/acs cannot flood the Redis pub/sub
bus while the AuditLog still records each rejection for SOC review.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)" -- backend/adhkar/audit.py backend/adhkar/api/v1/saml.py backend/tests/unit/test_audit_emit_flag.py
git tag v1.0.0-rc277.audit-emit-outbox-flag
```

---

## Task 5: CaseDetailPage "Your activity" badge

**Files:**
- Modify: `frontend/src/pages/CaseDetailPage.tsx`

- [ ] **Step 1: Read the current page header**

```bash
cd /Users/salma/Documents/Research/adhkar-ir && head -120 frontend/src/pages/CaseDetailPage.tsx | tail -60
```
Identify the case `<h1>` (around the page's header section). The badge will render immediately after that heading.

- [ ] **Step 2: Add the `MyContrib` interface and state**

In `CaseDetailPage.tsx`, near the existing interface declarations at the top of the component (the file already has `interface CaseLinkRow`, `interface AttachmentRow`, etc.), ADD:

```typescript
interface MyContrib {
  user_id: string;
  comment_count: number;
  task_log_count: number;
  audit_count: number;
}
```

Inside the component function, alongside the existing `useState` declarations, ADD:

```typescript
const [myContrib, setMyContrib] = useState<MyContrib | null>(null);
```

- [ ] **Step 3: Add the fetch effect**

Inside the component, after the existing `useEffect` blocks that fetch other case data, ADD:

```typescript
useEffect(() => {
  apiCall<MyContrib>(`/v1/cases/${caseId}/contributors/me`)
    .then(setMyContrib)
    .catch(() => setMyContrib(null));
}, [apiCall, caseId]);
```

- [ ] **Step 4: Render the badge under the page header**

Find the case `<h1>` element. Immediately AFTER it (still inside its container element), insert:

```tsx
{myContrib && (myContrib.comment_count + myContrib.task_log_count + myContrib.audit_count > 0) && (
  <aside className="mt-1 inline-flex items-center gap-2 rounded-full bg-md-sys-color-surface-container px-3 py-0.5 text-xs">
    <span className="font-medium">Your activity:</span>
    <span>{myContrib.comment_count} comments · {myContrib.task_log_count} task updates · {myContrib.audit_count} audits</span>
  </aside>
)}
```

- [ ] **Step 5: Run frontend validation**

```bash
cd /Users/salma/Documents/Research/adhkar-ir/frontend && pnpm typecheck && pnpm lint && pnpm test --run
```
Expected: typecheck clean, lint 0 warnings, all vitest tests pass.

- [ ] **Step 6: Commit + tag (path-scoped)**

```bash
cd /Users/salma/Documents/Research/adhkar-ir
git commit -s -m "$(cat <<'EOF'
feat(cases): your-activity badge on case detail page

Retry of the killed RC261. Consumes /v1/cases/{id}/contributors/me
(RC260 endpoint) and renders an inline badge under the case header
when the caller has any activity on the case. Hidden when the
counts sum to zero.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)" -- frontend/src/pages/CaseDetailPage.tsx
git tag v1.0.0-rc278.case-detail-your-activity
```

---

## Task 6: Hoist `services` fixture to integration `conftest.py` + SAML ACS happy-path test

**Files:**
- Create: `backend/tests/integration/conftest.py`
- Modify: `backend/tests/integration/test_readyz_integration.py`
- Create: `backend/tests/integration/test_saml_acs_happy_path.py`

The existing `test_readyz_integration.py` has a module-scoped `services` fixture that boots Postgres + Redis + MinIO. Lift it to `conftest.py` with `scope="session"` so the SAML happy-path test (and later CRUD tests) can reuse the same containers.

- [ ] **Step 1: Create the conftest with the lifted fixture**

Create `backend/tests/integration/conftest.py`:

```python
"""Shared session-scoped pg+redis+minio docker stack for integration tests.

Each test file consumes the `services` fixture and receives a dict of
URLs. Tests apply Alembic migrations at test setup time and roll back
per-test changes via savepoints (handled inside each test file).

In CI the fixture honors DATABASE_URL/REDIS_URL service-container env
vars and skips the docker boot. Local runs require Docker; missing
docker triggers pytest.skip, not test failure."""

from __future__ import annotations

import os

import pytest

DOCKER_AVAILABLE = os.environ.get("DOCKER_HOST") or os.path.exists("/var/run/docker.sock")
USE_SERVICES_FROM_ENV = bool(
    os.environ.get("DATABASE_URL") and os.environ.get("REDIS_URL") and not DOCKER_AVAILABLE
)


@pytest.fixture(scope="session")
def services():
    if USE_SERVICES_FROM_ENV:
        yield {
            "database_url": os.environ["DATABASE_URL"],
            "redis_url": os.environ["REDIS_URL"],
            "s3_endpoint": os.environ.get("ADHKAR_S3_ENDPOINT", "http://localhost:9000"),
            "s3_access_key": os.environ.get("ADHKAR_S3_ACCESS_KEY", "minio-dev"),
            "s3_secret_key": os.environ.get("ADHKAR_S3_SECRET_KEY", "minio-dev-secret"),
        }
        return

    if not DOCKER_AVAILABLE:
        pytest.skip("docker not available; set DATABASE_URL/REDIS_URL for service-mode")

    from testcontainers.minio import MinioContainer
    from testcontainers.postgres import PostgresContainer
    from testcontainers.redis import RedisContainer

    pg = PostgresContainer("pgvector/pgvector:pg16")
    rd = RedisContainer("redis:7-alpine")
    s3 = MinioContainer("minio/minio:latest")
    pg.start()
    rd.start()
    s3.start()
    try:
        yield {
            "database_url": pg.get_connection_url().replace(
                "postgresql+psycopg2://", "postgresql+asyncpg://"
            ),
            "redis_url": f"redis://{rd.get_container_host_ip()}:{rd.get_exposed_port(6379)}/0",
            "s3_endpoint": f"http://{s3.get_container_host_ip()}:{s3.get_exposed_port(9000)}",
            "s3_access_key": s3.access_key,
            "s3_secret_key": s3.secret_key,
        }
    finally:
        pg.stop()
        rd.stop()
        s3.stop()
```

- [ ] **Step 2: Strip the duplicate fixture from `test_readyz_integration.py`**

Open `backend/tests/integration/test_readyz_integration.py`. DELETE the existing `@pytest.fixture(scope="module") def services(): ...` block (everything from that decorator down through the matching `finally: pg.stop(); rd.stop(); s3.stop()`). Also DELETE the now-unused `DOCKER_AVAILABLE` and `USE_SERVICES_FROM_ENV` module-level constants if they were only used by the fixture (the test body may still reference them — if so, leave them).

Verify the test still resolves `services` via the conftest:
```bash
cd /Users/salma/Documents/Research/adhkar-ir/backend && \
  uv run pytest tests/integration/test_readyz_integration.py --collect-only -q
```
Expected: 1 test collected, no errors.

- [ ] **Step 3: Write the SAML happy-path integration test**

Create `backend/tests/integration/test_saml_acs_happy_path.py`:

```python
"""End-to-end SAML ACS test: signed assertion -> 200 + access_token.

Boots Postgres+Redis+MinIO via the session-scoped `services` fixture,
applies Alembic migrations once per session, then POSTs the
valid_response.xml fixture to /v1/auth/saml/test/acs and asserts the
issued token round-trip plus a saml_login audit row."""

from __future__ import annotations

import asyncio
import base64
import json
import pathlib
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from freezegun import freeze_time
from httpx import ASGITransport, AsyncClient

FIXTURES = pathlib.Path(__file__).parent.parent / "unit" / "fixtures" / "saml"
FROZEN_NOW = datetime(2026, 6, 17, 12, 0, 0, tzinfo=UTC)


@pytest_asyncio.fixture
async def app_with_verifier(services, monkeypatch):
    """Boot the app against real Postgres+Redis with a SAML verifier wired
    into app.state. Migrations apply once per session via _migrations_applied."""
    monkeypatch.setenv("DATABASE_URL", services["database_url"])
    monkeypatch.setenv("REDIS_URL", services["redis_url"])
    monkeypatch.setenv("ADHKAR_SECRET_KEY", "x" * 32)
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

    # Apply migrations (one-shot per session; idempotent on re-run).
    from alembic import command
    from alembic.config import Config

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", services["database_url"])
    await asyncio.to_thread(command.upgrade, cfg, "head")

    # Build the app and wire a SamlVerifier into app.state.
    from adhkar.auth.saml import SamlProviderConfig
    from adhkar.auth.saml_verifier import build_verifier_from_metadata_xml
    from adhkar.core.settings import Settings
    from adhkar.main import create_app

    app = create_app(Settings())
    cfg_obj = SamlProviderConfig(
        name="test",
        idp_entity_id="https://idp.test/saml/metadata",
        idp_sso_url="https://idp.test/saml/sso",
        sp_entity_id="https://adhkar.test/api/v1/auth/saml/test/metadata",
        acs_url="https://adhkar.test/v1/auth/saml/test/acs",
        metadata_url="https://idp.test/metadata",
        wanted_attributes={"email": "mail", "display_name": "displayName"},
    )
    metadata_xml = (FIXTURES / "valid_idp_metadata.xml").read_text()
    app.state.saml_verifiers = {"test": build_verifier_from_metadata_xml(cfg_obj, metadata_xml)}
    yield app


def _b64(name: str) -> str:
    return base64.b64encode((FIXTURES / name).read_bytes()).decode()


@pytest.mark.integration
@pytest.mark.asyncio
@freeze_time(FROZEN_NOW)
async def test_acs_with_valid_response_issues_access_token(app_with_verifier) -> None:
    transport = ASGITransport(app=app_with_verifier)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.post(
            "/v1/auth/saml/test/acs",
            data={"SAMLResponse": _b64("valid_response.xml"), "RelayState": ""},
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "access_token" in body and isinstance(body["access_token"], str)
    assert body["token_type"] == "bearer"
    assert body["user_id"]  # UUID string
```

- [ ] **Step 4: Run integration tests (will run only if docker is up)**

```bash
cd /Users/salma/Documents/Research/adhkar-ir/backend && \
  uv run pytest tests/integration/ -q -m integration
```
Expected: if docker available, `2 passed` (readyz + saml_acs_happy). If not, `2 skipped`.

Whether docker is available or not, the smoke test must remain green:
```bash
cd /Users/salma/Documents/Research/adhkar-ir/backend && uv run pytest tests/integration/test_openapi_route_coverage.py -q
```
Expected: 3 passed.

Run unit suite + lint:
```bash
cd /Users/salma/Documents/Research/adhkar-ir/backend && \
  uv run pytest tests/unit/ -q && \
  uv run ruff check tests/integration/conftest.py tests/integration/test_saml_acs_happy_path.py && \
  uv run ruff format tests/integration/conftest.py tests/integration/test_saml_acs_happy_path.py
```
Expected: clean.

- [ ] **Step 5: Commit + tag (path-scoped)**

```bash
cd /Users/salma/Documents/Research/adhkar-ir
git commit -s -m "$(cat <<'EOF'
test(integration): SAML ACS happy-path + session-scoped pg/redis/minio

Lifts the services fixture from test_readyz_integration.py into
conftest.py with scope="session" so the existing readyz test and the
new SAML happy-path share a single Postgres+Redis+MinIO triple. The
SAML happy-path test was deferred from RC272 because it needed a
live DB to mint tokens; it now POSTs valid_response.xml and asserts
the issued access_token round-trip.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)" -- backend/tests/integration/conftest.py backend/tests/integration/test_readyz_integration.py backend/tests/integration/test_saml_acs_happy_path.py
git tag v1.0.0-rc279.integration-stack-and-saml-happy
```

---

## Task 7: Cases CRUD integration test

**Files:**
- Create: `backend/tests/integration/test_cases_crud.py`

- [ ] **Step 1: Write the test**

Create `backend/tests/integration/test_cases_crud.py`:

```python
"""Integration: create -> patch -> soft-delete a case; verify audit trail."""

from __future__ import annotations

import asyncio

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


@pytest_asyncio.fixture
async def app_against_services(services, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", services["database_url"])
    monkeypatch.setenv("REDIS_URL", services["redis_url"])
    monkeypatch.setenv("ADHKAR_SECRET_KEY", "x" * 32)
    from adhkar.core.settings import get_settings

    get_settings.cache_clear()

    from alembic import command
    from alembic.config import Config

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", services["database_url"])
    await asyncio.to_thread(command.upgrade, cfg, "head")

    from adhkar.core.settings import Settings
    from adhkar.main import create_app

    return create_app(Settings())


async def _bootstrap_user_and_org(services) -> str:
    """Seed an org + admin user + JWT directly via the model layer. Returns
    the bearer access_token. org_id is encoded into the JWT (no separate
    request header — adhkar.api.deps.require_current_org reads it from
    user.org_id which get_current_user sets from the JWT claim)."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from adhkar.auth.password import hash_password
    from adhkar.auth.tokens import issue_tokens
    from adhkar.db.models import Organization, Profile, User, UserOrgMembership

    engine = create_async_engine(services["database_url"])
    Session = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with Session() as s:
            org = Organization(name="Test Org", slug="test-org")
            s.add(org)
            await s.flush()
            profile = Profile(
                organization_id=org.id,
                name="Admin",
                permissions=["manageCase", "viewCase"],
            )
            s.add(profile)
            await s.flush()
            u = User(
                email="case-crud@example.test",
                display_name="Case CRUD Tester",
                password_hash=hash_password("Sufficient-pw-123"),
                status="active",
                default_org_id=org.id,
            )
            s.add(u)
            await s.flush()
            s.add(UserOrgMembership(user_id=u.id, organization_id=org.id, profile_id=profile.id))
            tokens = await issue_tokens(
                session=s,
                user_id=u.id,
                org_id=org.id,
                perms=["manageCase", "viewCase"],
                secret="x" * 32,
            )
            await s.commit()
            return tokens.access_token
    finally:
        await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_case_create_patch_soft_delete_round_trip(app_against_services, services) -> None:
    access_token = await _bootstrap_user_and_org(services)
    headers = {"Authorization": f"Bearer {access_token}"}
    transport = ASGITransport(app=app_against_services)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        # Create
        r = await c.post(
            "/v1/cases",
            json={"title": "End-to-end test case", "severity": 3, "tlp": "amber"},
            headers=headers,
        )
        assert r.status_code == 201, r.text
        case_id = r.json()["id"]

        # Patch (escalate to severity 4 + add a tag)
        r = await c.patch(
            f"/v1/cases/{case_id}",
            json={"severity": 4, "tags": ["incident"]},
            headers=headers,
        )
        assert r.status_code == 200, r.text
        assert r.json()["severity"] == 4
        assert r.json()["tags"] == ["incident"]

        # Soft-delete
        r = await c.delete(f"/v1/cases/{case_id}", headers=headers)
        assert r.status_code == 204, r.text

        # Confirm gone from list
        r = await c.get("/v1/cases", headers=headers)
        assert r.status_code == 200
        assert all(c_["id"] != case_id for c_ in r.json())
```

- [ ] **Step 2: Run the integration tests**

```bash
cd /Users/salma/Documents/Research/adhkar-ir/backend && uv run pytest tests/integration/test_cases_crud.py -q -m integration
```
Expected: `1 passed` if docker available, `1 skipped` otherwise.

- [ ] **Step 3: Lint**

```bash
cd /Users/salma/Documents/Research/adhkar-ir/backend && \
  uv run ruff check tests/integration/test_cases_crud.py && \
  uv run ruff format tests/integration/test_cases_crud.py
```
Expected: clean.

- [ ] **Step 4: Commit + tag (path-scoped)**

```bash
cd /Users/salma/Documents/Research/adhkar-ir
git commit -s -m "$(cat <<'EOF'
test(integration): case CRUD round-trip against real Postgres

Bootstraps an org + admin user via the auth/tokens helpers, then
POSTs /v1/cases, PATCHes severity + tags, DELETEs (soft), and
confirms the case no longer appears in /v1/cases. Exercises the
audit trail at every mutation point.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)" -- backend/tests/integration/test_cases_crud.py
git tag v1.0.0-rc279a.integration-cases-crud
```

---

## Task 8: Alert promote-to-case integration test

**Files:**
- Create: `backend/tests/integration/test_alert_promote.py`

- [ ] **Step 1: Write the test**

Create `backend/tests/integration/test_alert_promote.py`:

```python
"""Integration: ingest alert -> promote to case -> verify wiring."""

from __future__ import annotations

import asyncio

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


@pytest_asyncio.fixture
async def app_against_services(services, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", services["database_url"])
    monkeypatch.setenv("REDIS_URL", services["redis_url"])
    monkeypatch.setenv("ADHKAR_SECRET_KEY", "x" * 32)
    from adhkar.core.settings import get_settings

    get_settings.cache_clear()

    from alembic import command
    from alembic.config import Config

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", services["database_url"])
    await asyncio.to_thread(command.upgrade, cfg, "head")

    from adhkar.core.settings import Settings
    from adhkar.main import create_app

    return create_app(Settings())


async def _bootstrap_user(services, perms: list[str]) -> str:
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from adhkar.auth.password import hash_password
    from adhkar.auth.tokens import issue_tokens
    from adhkar.db.models import Organization, Profile, User, UserOrgMembership

    engine = create_async_engine(services["database_url"])
    Session = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with Session() as s:
            org = Organization(name="Alert Promote Org", slug="alert-promote")
            s.add(org)
            await s.flush()
            profile = Profile(organization_id=org.id, name="Admin", permissions=perms)
            s.add(profile)
            await s.flush()
            u = User(
                email="alert-promote@example.test",
                display_name="Alert Promote Tester",
                password_hash=hash_password("Sufficient-pw-123"),
                status="active",
                default_org_id=org.id,
            )
            s.add(u)
            await s.flush()
            s.add(UserOrgMembership(user_id=u.id, organization_id=org.id, profile_id=profile.id))
            tokens = await issue_tokens(
                session=s, user_id=u.id, org_id=org.id, perms=perms, secret="x" * 32
            )
            await s.commit()
            return tokens.access_token
    finally:
        await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_alert_promote_creates_case_and_links_alert(app_against_services, services) -> None:
    token = await _bootstrap_user(
        services, ["manageAlert", "viewAlert", "manageCase", "viewCase"]
    )
    headers = {"Authorization": f"Bearer {token}"}
    transport = ASGITransport(app=app_against_services)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.post(
            "/v1/alerts",
            json={
                "type": "external",
                "source": "siem-test",
                "source_ref": "alert-1",
                "title": "Suspicious login",
                "severity": 3,
                "tlp": "amber",
            },
            headers=headers,
        )
        assert r.status_code == 201, r.text
        alert_id = r.json()["id"]

        r = await c.post(
            f"/v1/alerts/{alert_id}/promote",
            json={},
            headers=headers,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        case_id = body["case_id"]
        assert case_id

        # Confirm alert.case_id is set via the alerts list with ?case_id filter (RC250)
        r = await c.get(f"/v1/alerts?case_id={case_id}", headers=headers)
        assert r.status_code == 200
        ids = [a["id"] for a in r.json()]
        assert alert_id in ids
```

- [ ] **Step 2: Run**

```bash
cd /Users/salma/Documents/Research/adhkar-ir/backend && uv run pytest tests/integration/test_alert_promote.py -q -m integration
```
Expected: `1 passed` if docker available, else `1 skipped`.

- [ ] **Step 3: Lint + commit + tag**

```bash
cd /Users/salma/Documents/Research/adhkar-ir/backend && uv run ruff check tests/integration/test_alert_promote.py && uv run ruff format tests/integration/test_alert_promote.py
```

```bash
cd /Users/salma/Documents/Research/adhkar-ir
git commit -s -m "$(cat <<'EOF'
test(integration): alert promote -> case round-trip

POSTs an alert, promotes it, then uses the RC250 ?case_id= filter to
confirm the alert is now bound to the newly-created case.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)" -- backend/tests/integration/test_alert_promote.py
git tag v1.0.0-rc279b.integration-alert-promote
```

---

## Task 9: Observable attach integration test

**Files:**
- Create: `backend/tests/integration/test_observables_attach.py`

- [ ] **Step 1: Write the test**

Create `backend/tests/integration/test_observables_attach.py`:

```python
"""Integration: create observable -> attach to case -> similarity counts -> detach."""

from __future__ import annotations

import asyncio

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


@pytest_asyncio.fixture
async def app_against_services(services, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", services["database_url"])
    monkeypatch.setenv("REDIS_URL", services["redis_url"])
    monkeypatch.setenv("ADHKAR_SECRET_KEY", "x" * 32)
    from adhkar.core.settings import get_settings

    get_settings.cache_clear()

    from alembic import command
    from alembic.config import Config

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", services["database_url"])
    await asyncio.to_thread(command.upgrade, cfg, "head")

    from adhkar.core.settings import Settings
    from adhkar.main import create_app

    return create_app(Settings())


async def _bootstrap(services, perms: list[str]) -> str:
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from adhkar.auth.password import hash_password
    from adhkar.auth.tokens import issue_tokens
    from adhkar.db.models import Organization, Profile, User, UserOrgMembership

    engine = create_async_engine(services["database_url"])
    Session = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with Session() as s:
            org = Organization(name="Obs Attach Org", slug="obs-attach")
            s.add(org)
            await s.flush()
            profile = Profile(organization_id=org.id, name="Admin", permissions=perms)
            s.add(profile)
            await s.flush()
            u = User(
                email="obs-attach@example.test",
                display_name="Obs Attach Tester",
                password_hash=hash_password("Sufficient-pw-123"),
                status="active",
                default_org_id=org.id,
            )
            s.add(u)
            await s.flush()
            s.add(UserOrgMembership(user_id=u.id, organization_id=org.id, profile_id=profile.id))
            tokens = await issue_tokens(
                session=s, user_id=u.id, org_id=org.id, perms=perms, secret="x" * 32
            )
            await s.commit()
            return tokens.access_token
    finally:
        await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_observable_attach_detach_round_trip(app_against_services, services) -> None:
    token = await _bootstrap(
        services, ["manageCase", "viewCase", "manageObservable", "viewObservable"]
    )
    headers = {"Authorization": f"Bearer {token}"}
    transport = ASGITransport(app=app_against_services)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        # Create case
        r = await c.post(
            "/v1/cases",
            json={"title": "Obs round-trip", "severity": 2, "tlp": "amber"},
            headers=headers,
        )
        case_id = r.json()["id"]

        # Create observable (unattached)
        r = await c.post(
            "/v1/observables",
            json={"data_type": "ip", "data": "203.0.113.7", "tlp": "amber", "is_ioc": True},
            headers=headers,
        )
        assert r.status_code == 201, r.text
        obs_id = r.json()["id"]

        # Attach
        r = await c.post(
            f"/v1/cases/{case_id}/observables/attach",
            json={"observable_ids": [obs_id]},
            headers=headers,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["attached"] == 1

        # Confirm via per-case list
        r = await c.get(f"/v1/cases/{case_id}/observables", headers=headers)
        assert r.status_code == 200
        assert obs_id in [o["id"] for o in r.json()]

        # Detach
        r = await c.post(
            f"/v1/cases/{case_id}/observables/{obs_id}/detach",
            headers=headers,
        )
        assert r.status_code == 204, r.text

        # Confirm no longer on the case
        r = await c.get(f"/v1/cases/{case_id}/observables", headers=headers)
        assert r.status_code == 200
        assert obs_id not in [o["id"] for o in r.json()]
```

- [ ] **Step 2: Run + lint + commit + tag**

```bash
cd /Users/salma/Documents/Research/adhkar-ir/backend && \
  uv run pytest tests/integration/test_observables_attach.py -q -m integration && \
  uv run ruff check tests/integration/test_observables_attach.py && \
  uv run ruff format tests/integration/test_observables_attach.py
```

```bash
cd /Users/salma/Documents/Research/adhkar-ir
git commit -s -m "$(cat <<'EOF'
test(integration): observable attach + detach round-trip

Creates an IoC observable + a case, attaches the observable, confirms
it shows up in /v1/cases/{id}/observables, detaches it, and confirms
it disappears.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)" -- backend/tests/integration/test_observables_attach.py
git tag v1.0.0-rc279c.integration-observables-attach
```

---

## Task 10: Notification dispatch integration test

**Files:**
- Create: `backend/tests/integration/test_notifications_dispatch.py`

- [ ] **Step 1: Write the test**

Create `backend/tests/integration/test_notifications_dispatch.py`:

```python
"""Integration: endpoint + rule + event -> NotificationDelivery succeeded."""

from __future__ import annotations

import asyncio

import pytest
import pytest_asyncio
import respx
from httpx import ASGITransport, AsyncClient, Response


@pytest_asyncio.fixture
async def app_against_services(services, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", services["database_url"])
    monkeypatch.setenv("REDIS_URL", services["redis_url"])
    monkeypatch.setenv("ADHKAR_SECRET_KEY", "x" * 32)
    from adhkar.core.settings import get_settings

    get_settings.cache_clear()

    from alembic import command
    from alembic.config import Config

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", services["database_url"])
    await asyncio.to_thread(command.upgrade, cfg, "head")

    from adhkar.core.settings import Settings
    from adhkar.main import create_app

    return create_app(Settings())


async def _bootstrap(services, perms: list[str]) -> str:
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from adhkar.auth.password import hash_password
    from adhkar.auth.tokens import issue_tokens
    from adhkar.db.models import Organization, Profile, User, UserOrgMembership

    engine = create_async_engine(services["database_url"])
    Session = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with Session() as s:
            org = Organization(name="Notify Org", slug="notify")
            s.add(org)
            await s.flush()
            profile = Profile(organization_id=org.id, name="Admin", permissions=perms)
            s.add(profile)
            await s.flush()
            u = User(
                email="notify@example.test",
                display_name="Notify Tester",
                password_hash=hash_password("Sufficient-pw-123"),
                status="active",
                default_org_id=org.id,
            )
            s.add(u)
            await s.flush()
            s.add(UserOrgMembership(user_id=u.id, organization_id=org.id, profile_id=profile.id))
            tokens = await issue_tokens(
                session=s, user_id=u.id, org_id=org.id, perms=perms, secret="x" * 32
            )
            await s.commit()
            return tokens.access_token
    finally:
        await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_endpoint_test_button_records_succeeded_delivery(
    app_against_services, services
) -> None:
    """The simplest end-to-end is the endpoint Test button (RC88) which
    fires a synthetic event through the dispatcher and writes a
    NotificationDelivery row. We mock the upstream webhook with respx."""
    token = await _bootstrap(services, ["manageConfig"])
    headers = {"Authorization": f"Bearer {token}"}
    transport = ASGITransport(app=app_against_services)

    with respx.mock:
        respx.post("https://hooks.example/webhook").mock(return_value=Response(200, text="ok"))

        async with AsyncClient(transport=transport, base_url="http://t") as c:
            # Create webhook endpoint
            r = await c.post(
                "/v1/notification-endpoints",
                json={
                    "name": "test-hook",
                    "kind": "webhook",
                    "config": {"url": "https://hooks.example/webhook"},
                    "enabled": True,
                },
                headers=headers,
            )
            assert r.status_code == 201, r.text
            endpoint_id = r.json()["id"]

            # Fire the synthetic test
            r = await c.post(
                f"/v1/notification-endpoints/{endpoint_id}/test",
                headers=headers,
            )
            assert r.status_code == 200, r.text
            assert r.json()["ok"] is True

    # Confirm the NotificationDelivery row is present and succeeded (outside the respx context).
    async with AsyncClient(transport=transport, base_url="http://t") as c2:
        r = await c2.get(
            f"/v1/notification-deliveries?endpoint_id={endpoint_id}",
            headers=headers,
        )
        assert r.status_code == 200
        deliveries = r.json()
        assert any(d["status"] == "succeeded" for d in deliveries)
```

- [ ] **Step 2: Run + lint + commit + tag**

```bash
cd /Users/salma/Documents/Research/adhkar-ir/backend && \
  uv run pytest tests/integration/test_notifications_dispatch.py -q -m integration && \
  uv run ruff check tests/integration/test_notifications_dispatch.py && \
  uv run ruff format tests/integration/test_notifications_dispatch.py
```

```bash
cd /Users/salma/Documents/Research/adhkar-ir
git commit -s -m "$(cat <<'EOF'
test(integration): notification dispatcher end-to-end via endpoint test button

Mocks the upstream webhook with respx, creates a notification endpoint,
fires the RC88 synthetic test event, and asserts the NotificationDelivery
row was written with status=succeeded.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)" -- backend/tests/integration/test_notifications_dispatch.py
git tag v1.0.0-rc279d.integration-notifications
```

---

## Task 11: Plan doc + memory snapshot + `v1.0.0` tag

**Files:**
- Commit: `docs/superpowers/plans/2026-06-18-phase10-closeout.md` (this file)
- Modify: `/Users/salma/.claude/projects/-Users-salma-Documents-Research-TheBee/memory/project-adhkar-ir.md`

- [ ] **Step 1: Final validation across the suite**

```bash
cd /Users/salma/Documents/Research/adhkar-ir/backend && \
  uv run ruff check --fix . && \
  uv run ruff format . && \
  uv run mypy adhkar && \
  OTEL_SDK_DISABLED=true uv run pytest tests/ -q
```
Expected: ruff clean, mypy clean, full suite passes (~210 with the new tests).

If integration tests skipped because docker unavailable, run unit-only:
```bash
cd /Users/salma/Documents/Research/adhkar-ir/backend && OTEL_SDK_DISABLED=true uv run pytest tests/unit/ -q
```
Expected: all unit tests pass (~206 unit tests including the new ones).

- [ ] **Step 2: Commit the plan doc**

```bash
cd /Users/salma/Documents/Research/adhkar-ir
git add docs/superpowers/plans/2026-06-18-phase10-closeout.md
git commit -s -m "$(cat <<'EOF'
docs(plans): Phase 10 closeout implementation plan

Captures the 11-task plan that delivers RC275-RC279d (xmlsec1 README,
source_ip helper sweep, audit emit_outbox flag, CaseDetail your-activity
badge, and a 5-test critical-path testcontainers integration suite).
Companion to docs/superpowers/specs/2026-06-18-adhkar-phase10-closeout-design.md.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 3: Append the closeout snapshot to project memory**

Open `/Users/salma/.claude/projects/-Users-salma-Documents-Research-TheBee/memory/project-adhkar-ir.md`. Find the existing RC263-RC272 snapshot (around line 29) and insert ABOVE it:

```markdown
- **Phase 10 closeout — 2026-06-18 — branch `phase10/hardening`, tag `v1.0.0`** — RC275 README xmlsec1 note · RC276 source_ip helper + RC276a call-site sweep (audit + ratelimit honor X-Forwarded-For) · RC277 audit_and_emit emit_outbox flag (SAML ACS opts out so scraper junk can't flood Redis pub/sub) · RC278 CaseDetail your-activity badge (RC261 retry, consumes RC260) · RC279 SAML happy-path integration test + session-scoped pg/redis/minio conftest fixture · RC279a-d cases CRUD / alert promote / observable attach / notification dispatch integration tests · v1.0.0 lightweight tag at RC279d's commit + this plan doc commit. Closes Phase 10. Spec at docs/superpowers/specs/2026-06-18-adhkar-phase10-closeout-design.md.
```

Save the file (no git involved — memory dir is not a git repo).

- [ ] **Step 4: Tag `v1.0.0`**

```bash
cd /Users/salma/Documents/Research/adhkar-ir
# Tag the current HEAD (the plan-doc commit) as v1.0.0.
git tag v1.0.0
git log --oneline -15
```

The git log output should show the plan-doc commit at HEAD, the 6 RC commits (RC275-RC279d), and the spec doc commit (`ba75562`) reachable.

- [ ] **Step 5: Confirm tags**

```bash
cd /Users/salma/Documents/Research/adhkar-ir && git tag | grep -E "v1.0.0(\b|-rc275|-rc276|-rc277|-rc278|-rc279)" | sort -V
```
Expected (or similar):
```
v1.0.0
v1.0.0-rc275.readme-xmlsec1
v1.0.0-rc276.source-ip-helper
v1.0.0-rc276a.source-ip-callsite-sweep
v1.0.0-rc277.audit-emit-outbox-flag
v1.0.0-rc278.case-detail-your-activity
v1.0.0-rc279.integration-stack-and-saml-happy
v1.0.0-rc279a.integration-cases-crud
v1.0.0-rc279b.integration-alert-promote
v1.0.0-rc279c.integration-observables-attach
v1.0.0-rc279d.integration-notifications
```

---

## Coverage check (run after Task 11)

| Spec requirement | Task |
|------------------|------|
| README `xmlsec1` prerequisite | Task 1 |
| `source_ip` helper module | Task 2 |
| Helper sweep across 5 call sites | Task 3 |
| `audit_and_emit(emit_outbox=...)` flag + SAML ACS opt-out | Task 4 |
| CaseDetail your-activity badge (RC261 retry) | Task 5 |
| Session-scoped pg+redis+minio conftest fixture | Task 6 |
| SAML happy-path 200 integration test | Task 6 |
| Cases CRUD integration test | Task 7 |
| Alert promote integration test | Task 8 |
| Observable attach integration test | Task 9 |
| Notification dispatch integration test | Task 10 |
| `v1.0.0` lightweight tag + memory snapshot + plan commit | Task 11 |

Every spec requirement has a task. No placeholders. Cross-task references match (`source_ip(request)` signature; `audit_and_emit(..., emit_outbox=False)` keyword; `services` fixture name).

---

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-18-phase10-closeout.md`. Two execution options:

**1. Subagent-Driven (recommended)** — fresh implementer subagent per task, two-stage review (spec + code quality) between tasks.

**2. Inline Execution** — execute the 11 tasks in this session via the executing-plans skill.

Which approach?
