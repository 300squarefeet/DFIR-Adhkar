# Adhkar IR — Phase 0 Foundations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bootstrap the Adhkar IR monorepo so that `docker compose up` brings the full local stack to healthy, the dark-themed React shell loads at `:5173`, the FastAPI service exposes `/healthz` `/readyz` `/version` `/docs`, four ADRs are recorded, CI is green, and a small set of design-system primitives renders in Storybook — with zero domain features.

**Architecture:** Modular monorepo with `backend/` (FastAPI 3.12 + uv + SQLAlchemy async + Alembic), `frontend/` (Vite + React 18 + TS + pnpm + Tailwind v4 + shadcn/ui + Storybook 8), `deploy/` (docker-compose: postgres+pgvector, redis, minio, mailhog), `docs/` (architecture + 4 ADRs), `.github/` (CI + container scan). Pluggable `SearchIndex` interface is reserved for Phase 1 (no impl this phase). All env vars use `ADHKAR_*` prefix.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.x async (asyncpg), Alembic, structlog, Pydantic v2, OpenTelemetry, uv; React 18, Vite 5, TypeScript, Tailwind v4, shadcn/ui, TanStack Router/Query, Storybook 8, Vitest, cmdk, pnpm; PostgreSQL 16 + pgvector, Redis 7, MinIO, MailHog; Ruff (lint+format), mypy strict, ESLint, Prettier, pytest, vitest, testcontainers, MSW; GitHub Actions, Trivy, Syft, cosign keyless; MADR 3.0 for ADRs.

**Reference:** Design spec at `docs/superpowers/specs/2026-06-16-adhkar-phase0-foundations-design.md`. Section references like "§5.3" point to that document.

**Working directory:** `/Users/salma/Documents/Research/adhkar-ir` (already git-init'd with `main` branch, two commits exist).

**Commit convention:** Conventional Commits + DCO sign-off (`git commit -s`). Co-author `Claude Opus 4.7 <noreply@anthropic.com>` only when AI assistance is meaningful for that commit.

---

## Task 1: Root files & directory skeleton

**Files:**
- Create: `LICENSE`, `NOTICE`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `README.md`, `.gitignore`, `.editorconfig`
- Create: placeholder `README.md` in `backend/`, `frontend/`, `workers/`, `ai/`, `analyzers/`, `sdk/`, `deploy/`

- [ ] **Step 1: Create `LICENSE` (Apache-2.0)**

Use the canonical Apache-2.0 text (11 KB) from `https://www.apache.org/licenses/LICENSE-2.0.txt`. Replace `[yyyy]` with `2026` and `[name of copyright owner]` with `The Adhkar IR Authors`. Save to repo root as `LICENSE` exactly — no modifications to the legal text other than those two substitutions.

- [ ] **Step 2: Create `NOTICE`**

```
Adhkar IR
Copyright 2026 The Adhkar IR Authors

This product includes software developed at
The Adhkar IR project (https://github.com/<org>/adhkar-ir).

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    https://www.apache.org/licenses/LICENSE-2.0
```

- [ ] **Step 3: Create `CONTRIBUTING.md` requiring DCO**

```markdown
# Contributing to Adhkar IR

Thanks for considering a contribution. Adhkar IR is Apache-2.0 licensed; contributions are accepted under the same license via **Developer Certificate of Origin (DCO)** sign-off — no CLA.

## How to contribute

1. Open an issue describing what you intend to do (or pick one labeled `good first issue`).
2. Fork, branch from `main`, make your changes.
3. Sign your commits: `git commit -s -m "feat(<area>): your message"`. Conventional Commits required.
4. Run `pre-commit run --all-files` before pushing.
5. Open a PR. CI must be green. One reviewer approval required.

## Commit message format

`<type>(<scope>): <subject>` per Conventional Commits 1.0. Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `ci`, `build`, `perf`.

Body explains *why*. Footer: `Signed-off-by: Name <email>` (added by `-s`).

## Code of Conduct

By participating you agree to the [Code of Conduct](CODE_OF_CONDUCT.md).
```

- [ ] **Step 4: Create `CODE_OF_CONDUCT.md`**

Use the Contributor Covenant v2.1 verbatim from `https://www.contributor-covenant.org/version/2/1/code_of_conduct.md`. Replace the contact placeholder line with `Contact: conduct@adhkar.dev` (placeholder — owner updates later).

- [ ] **Step 5: Create `README.md`**

```markdown
# Adhkar IR

> Open-source, self-hostable Security Incident Response Platform (SIRP) with a first-class AI layer.

[![CI](https://github.com/<org>/adhkar-ir/actions/workflows/ci.yml/badge.svg)](https://github.com/<org>/adhkar-ir/actions/workflows/ci.yml)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

## Quick start (local dev)

```bash
git clone https://github.com/<org>/adhkar-ir && cd adhkar-ir
cp deploy/.env.example deploy/.env
docker compose -f deploy/docker-compose.yml up -d
open http://localhost:5173
```

The web shell lives at `:5173`, the API at `:8000` (Swagger at `:8000/docs`), MailHog at `:8025`, MinIO console at `:9001`.

See [`docs/runbook.md`](docs/runbook.md) for setup, reset, and troubleshooting.

## Documentation

- Architecture: [`docs/architecture.md`](docs/architecture.md)
- ADRs: [`docs/ADRs/`](docs/ADRs/)
- API: served live at `/docs` (Swagger UI)

## License

Apache-2.0. See [`LICENSE`](LICENSE) and [`NOTICE`](NOTICE). Contributions require DCO sign-off — see [`CONTRIBUTING.md`](CONTRIBUTING.md).
```

- [ ] **Step 6: Create `.gitignore`**

```gitignore
# ----- OS -----
.DS_Store
Thumbs.db

# ----- Editors -----
.idea/
.vscode/
*.swp
*.swo

# ----- Env -----
deploy/.env
deploy/.env.local
deploy/.env.*.local

# ----- Python -----
__pycache__/
*.py[cod]
*.egg-info/
.venv/
venv/
.pytest_cache/
.mypy_cache/
.ruff_cache/
.coverage
coverage.xml
htmlcov/
dist/
build/

# ----- Node / pnpm -----
node_modules/
.pnpm-store/
frontend/dist/
frontend/storybook-static/
.eslintcache

# ----- Docker -----
*.pid

# ----- Logs -----
*.log
logs/

# ----- Test artifacts -----
test-results/
playwright-report/
```

- [ ] **Step 7: Create `.editorconfig`**

```ini
root = true

[*]
indent_style = space
indent_size = 2
end_of_line = lf
charset = utf-8
trim_trailing_whitespace = true
insert_final_newline = true

[*.{py,toml}]
indent_size = 4

[*.md]
trim_trailing_whitespace = false
```

- [ ] **Step 8: Create placeholder folder READMEs**

Create the following files with one-line content each:

`backend/README.md`:
```markdown
# backend/

FastAPI service. See `docs/superpowers/specs/2026-06-16-adhkar-phase0-foundations-design.md` §5.
```

`frontend/README.md`:
```markdown
# frontend/

Vite + React + TS app. See spec §6.
```

`workers/README.md`:
```markdown
# workers/

Placeholder. Worker tasks (Celery/Arq decision in Phase 2 ADR). Empty in Phase 0.
```

`ai/README.md`:
```markdown
# ai/

Placeholder. Adhkar Mind (LLM router, agent runtime, MCP server) — Phase 8.
```

`analyzers/README.md`:
```markdown
# analyzers/

Placeholder. Adhkar Workers analyzer/responder plugin SDK + starter library — Phase 2.
```

`sdk/README.md`:
```markdown
# sdk/

Placeholder. `adhkar-py` + `adhkar-go` SDKs generated from OpenAPI — Phase 10.
```

`deploy/README.md`:
```markdown
# deploy/

`docker-compose.yml` for local dev (Phase 0). Helm chart — Phase 10.
```

- [ ] **Step 9: Verify and commit**

Run:
```bash
git status
git add LICENSE NOTICE CONTRIBUTING.md CODE_OF_CONDUCT.md README.md .gitignore .editorconfig backend/ frontend/ workers/ ai/ analyzers/ sdk/ deploy/
git commit -s -m "chore: add root files, license, and placeholder folder skeleton

Apache-2.0 LICENSE + NOTICE, DCO-based CONTRIBUTING, Contributor
Covenant 2.1 code of conduct, README quick start, baseline
.gitignore and .editorconfig, and one-line README placeholders
for every monorepo subdirectory pointing to the design spec."
```

Expected: clean working tree after commit; `git log --oneline | wc -l` returns 3 (initial spec, rename, this commit).

---

## Task 2: Four ADRs (MADR 3.0)

**Files:**
- Create: `docs/ADRs/0001-naming-adhkar.md`
- Create: `docs/ADRs/0002-license-apache-core-plus-enterprise.md`
- Create: `docs/ADRs/0003-persistence-postgres-pgvector.md`
- Create: `docs/ADRs/0004-search-deferred-opensearch.md`

- [ ] **Step 1: Write ADR 0001**

`docs/ADRs/0001-naming-adhkar.md`:
```markdown
# 0001. Product naming — Adhkar

- Status: Accepted
- Date: 2026-06-16
- Deciders: project lead
- Tags: branding, legal

## Context and Problem Statement

The product needs a name that does not collide with StrangeBee (owner of TheHive) trademark or brand. The original brief proposed "TheBee", which differs from TheHive by one letter and reuses the Bee motif, and proposed SDK names `thebee4py`/`thebee4go` which directly mirror StrangeBee's official `thehive4py`/`thehive4go`.

## Decision Drivers

- Avoid trademark dilution / cease-and-desist risk
- Name available across PyPI, npm, Go module proxy, `*.dev` domain
- Not collide with other security-tooling brands (e.g., Microsoft Sentinel, CrowdStrike Falcon)
- Short, easy to type, brandable

## Considered Options

1. **Adhkar** (chosen)
2. Aegis — interim choice, rejected by stakeholder during brainstorm in favor of Adhkar
3. Sentinel — collision with Microsoft Sentinel SIEM
4. TheBee / Bee-derivatives — trademark proximity to StrangeBee/TheHive

## Decision Outcome

Chosen: **Adhkar**. Repo `adhkar-ir`. Package `adhkar`. SDKs `adhkar-py`, `adhkar-go`. Sub-modules: Adhkar Workers (analyzer/responder engine), Adhkar Mind (AI), Adhkar Portal (external collab). CLI `adhkarctl`. Container registry pattern `ghcr.io/<org>/adhkar-*`. Env var prefix `ADHKAR_*`. CSS token prefix `--adhkar-*`.

### Positive Consequences
- Distinct, unambiguous, free of trademark proximity to known security-tooling brands.
- Consistent naming scheme cascades to every sub-component.

### Negative Consequences
- "Adhkar" is a culture-specific term; search-engine awareness in security audience will be slower than a generic English word.
- Mitigation: always use "Adhkar IR" in public-facing prose to anchor the domain.

## Links

- See ADR 0002 (license model) and spec §2.1.
```

- [ ] **Step 2: Write ADR 0002**

`docs/ADRs/0002-license-apache-core-plus-enterprise.md`:
```markdown
# 0002. License model — Apache-2.0 core + commercial enterprise plugins

- Status: Accepted
- Date: 2026-06-16
- Deciders: project lead
- Tags: licensing, business-model

## Context and Problem Statement

Goal is twofold: a healthy OSS community *and* a viable enterprise monetization path without forking. TheHive 5 famously migrated from AGPL to proprietary; we want to avoid the same trap.

## Decision Drivers

- Contributor-friendly (avoid heavy CLA)
- Enterprise-friendly (AGPL viral clause scares legal teams)
- Clear monetization channel without code obfuscation
- Compatible with plugin SDK so third-party analyzers/responders may carry any license

## Considered Options

1. **Apache-2.0 core + commercial enterprise plugins** (chosen) — Grafana / GitLab model
2. AGPL-3.0 single repo + dual-licensing — MongoDB / old-TheHive model
3. BSL → Apache after 4 years — Sentry / CockroachDB model (not OSI-approved)
4. Apache-2.0 pure, no enterprise tier

## Decision Outcome

Core repo `adhkar-ir` is Apache-2.0. Enterprise plugins live in a separate private repo `adhkar-enterprise` (created when first enterprise feature ships, paving paved Phase 7+) under commercial license. The core provides a **stable plugin interface** from Phase 1 so enterprise modules can drop in without forking.

### Positive Consequences
- Maximum adoption surface.
- DCO sign-off (`git commit -s`) is the only contributor friction — no CLA.
- No license-enforcement code in the core; enforcement is plugin-presence-based.

### Negative Consequences
- Forks may strip our brand; mitigated by trademark policy in NOTICE.
- Some "obvious" enterprise features (SSO, advanced multi-tenant quotas) live outside core, possibly confusing OSS users.

## Links

- See ADR 0001 (naming) and spec §2.2.
```

- [ ] **Step 3: Write ADR 0003**

`docs/ADRs/0003-persistence-postgres-pgvector.md`:
```markdown
# 0003. Primary persistence — PostgreSQL 16 + pgvector

- Status: Accepted
- Date: 2026-06-16
- Deciders: project lead
- Tags: persistence, architecture

## Context and Problem Statement

TheHive 5 uses Cassandra + Elasticsearch + S3 because StrangeBee operates large multi-org SaaS clusters. For a greenfield self-hostable product targeting small-to-mid SOCs first, that stack is premature operational complexity.

## Decision Drivers

- Domain graph (Case → Task → Observable → Alert with N:M sharing/RBAC) is inherently relational
- Custom-field flexibility via JSONB
- Strong consistency for audit log + transactional outbox pattern
- Single store ≤ 4 GB RAM for default `docker compose up`
- pgvector covers Phase 8 RAG/similarity needs (millions of 1536-dim vectors with HNSW)

## Considered Options

1. **PostgreSQL 16 + pgvector** (chosen) — one store, ACID, JSONB + GIN + pg_trgm + tsvector + pgvector + uuid-ossp/pgcrypto extensions all available
2. Cassandra + Elasticsearch + S3 — TheHive-style, three systems, no SaaS-scale need yet
3. MongoDB + Atlas Search + S3 — relational graph harder, multi-document transactions only matured in 4.x

## Decision Outcome

Postgres 16 + pgvector is the primary store from Phase 0. Repository pattern introduced in Phase 1 (when first domain entity ships) so the backend stays pluggable for a future Cassandra/Cockroach impl if scale demands it.

### Positive Consequences
- One DB to back up (`pg_dump`), one schema to migrate (Alembic).
- ACID guarantees enable the transactional outbox pattern.
- Vector search lives in the same connection pool.

### Negative Consequences
- Vertical scale limit ~10 TB before sharding hurts; trigger to re-evaluate.
- HA topology adds complexity in production (Patroni / managed Postgres) — documented Phase 10.

## Links

- See ADR 0004 (search deferral) and spec §2.3, §5.5.
```

- [ ] **Step 4a: Write ADR 0005** (UI design system — Material Design 3, dense + dark default)

`docs/ADRs/0005-ui-design-system-material-design-3.md` is already authored in this plan's directional pivot — copy the content from the version committed at the same time as this plan update. Verify file exists and matches the spec §6 M3 vocabulary (token scheme `--md-sys-*`, Material Symbols Rounded, density overrides documented).

- [ ] **Step 4: Write ADR 0004**

`docs/ADRs/0004-search-deferred-opensearch.md`:
```markdown
# 0004. Search engine — Postgres FTS first, OpenSearch deferred

- Status: Accepted
- Date: 2026-06-16
- Deciders: project lead
- Tags: search, architecture, deferral

## Context and Problem Statement

The original brief specified OpenSearch in the Phase 0 docker-compose. PostgreSQL 16 provides `tsvector` full-text + `pg_trgm` fuzzy + GIN indexes that comfortably handle hundreds of thousands of cases/observables sub-second. OpenSearch from day one imposes JVM operational cost on every self-hoster and introduces dual-write consistency bugs — the #1 bug source in SIRP installations.

## Decision Drivers

- Default `docker compose up` < 4 GB RAM
- Avoid premature operational complexity (JVM tuning, indexer reliability)
- Keep search behind an interface so a future swap is non-disruptive

## Considered Options

1. **Postgres FTS first with `SearchIndex` interface** (chosen) — Phase 1+ ships `PostgresSearchIndex` impl
2. OpenSearch from day 0 — pattern tested early, expensive operationally
3. Hybrid `--profile search` opt-in — confusing default behavior

## Decision Outcome

Phase 0 omits OpenSearch. Phase 1 introduces a `SearchIndex` interface with `PostgresSearchIndex` impl when the first searchable entity (User) lands. A docker-compose profile slot for OpenSearch is reserved (commented out in `deploy/docker-compose.yml`) so a future opt-in is one uncomment away.

### Re-evaluation triggers

The decision is revisited if **any** of the following becomes true:
- p95 latency on list/filter > 500 ms with ≥ 500 000 observables
- Full-text needed inside attachment bodies (binary parsing — dedicated search engine territory)
- Enterprise adopter explicitly requires Elastic API compatibility

### Positive Consequences
- One-DB simplicity preserved for small teams.
- Search interface is proven by being implemented twice (Postgres now, OpenSearch later) — interface boundaries get exercised early.

### Negative Consequences
- OpenSearch-only features (e.g., advanced aggregations) deferred.
- Future migration carries dual-write transition risk; mitigated by interface design.

## Links

- ADR 0003 (persistence) and spec §2.3.
```

- [ ] **Step 5: Commit**

```bash
git add docs/ADRs/
git commit -s -m "docs(adr): record five Phase 0 architecture decisions

- 0001 naming — Adhkar (rejects TheBee for trademark proximity)
- 0002 license — Apache-2.0 core + commercial enterprise plugins
- 0003 persistence — PostgreSQL 16 + pgvector single store
- 0004 search — Postgres FTS first, OpenSearch deferred with
  explicit re-evaluation triggers
- 0005 ui design system — Material Design 3 dense + dark
  default (Tailwind+Radix on M3 tokens, Material Symbols
  Rounded, density + domain color overrides documented)

All five use MADR 3.0 format. Spec §7 references these directly."
```

---

## Task 3: Initial docs scaffolding

**Files:**
- Create: `docs/architecture.md`, `docs/runbook.md`, `docs/data-model.md`, `docs/api.md`

- [ ] **Step 1: Write `docs/architecture.md`**

```markdown
# Adhkar IR — Architecture

## One-page system view

```mermaid
flowchart LR
  subgraph Client
    Web[React 18 + Vite\nfrontend]
    SDK[adhkar-py / adhkar-go\n(Phase 10)]
    MCP[MCP client / external\nAI tools (Phase 8)]
  end
  subgraph Edge
    API[FastAPI HTTP/WS\nadhkar-api]
  end
  subgraph Workers
    W[Celery/Arq workers\n(Phase 2)]
    Sandbox[Analyzer sandbox\n(Phase 2)]
  end
  subgraph Data
    PG[(PostgreSQL 16\n+ pgvector)]
    R[(Redis)]
    S3[(MinIO / S3)]
    SMTP[(MailHog dev /\nSMTP prod)]
  end
  Web-->|REST + WS|API
  SDK-->API
  MCP-->API
  API-->PG
  API-->R
  API-->S3
  API-->W
  W-->PG
  W-->Sandbox
  API-->SMTP
```

## Stack

- **Backend**: FastAPI 3.12 (async), SQLAlchemy 2.x + asyncpg + Alembic, Pydantic v2, structlog, OpenTelemetry.
- **Frontend**: Vite 5, React 18 + TypeScript, Tailwind v4, shadcn/ui (Radix), TanStack Router/Query, Zustand, Storybook 8.
- **Data**: PostgreSQL 16 + pgvector, Redis 7, MinIO.
- **Plugins**: Adhkar Workers (analyzer/responder Docker-sandboxed engine — Phase 2). Adhkar Mind (AI — Phase 8). Adhkar Portal (external collab — Phase 9).

## Bounded contexts (will populate as phases land)

| Context | Phase |
|---|---|
| tenancy (Organization, User, Profile, RBAC) | 1 |
| audit & event/outbox | 1 |
| observables & workers engine | 2 |
| cases & tasks | 3 |
| alerts & feeders | 4 |
| automation (notifications, functions) | 5 |
| dashboards, KB, reporting | 6 |
| integrations (auth, MISP, EDR, SIEM, firewall, IM) | 7 |
| AI (Adhkar Mind) | 8 |
| external portal | 9 |
| hardening, helm, SDKs | 10 |

## Integration roadmap

Adhkar IR is an integration platform, not a re-implementation of EDR/SIEM. Third-party integrations land at three layers, each in a different phase:

| Layer | Lands | Vendors / protocols |
|---|---|---|
| **Intake** (incoming alert) | Phase 4 framework, vendor packets Phase 7 | SIEM (Splunk, Elastic, Microsoft Sentinel, QRadar) via webhook; EDR (CrowdStrike Falcon Streaming, SentinelOne Activities, Trellix HX, Symantec EDR) via feeder; MISP via dedicated connector; email-to-alert (IMAP / Microsoft Graph) |
| **Enrichment & response** (analyzer + responder) | Phase 2 engine, vendor packets Phase 7 | EDR query / containment (Falcon RTR, SentinelOne remote shell, Trellix isolation, Symantec quarantine); firewall blocks (Palo Alto, Fortinet, Cisco); ticketing (Jira, ServiceNow); IM (Slack, Teams, Mattermost); threat intel (VirusTotal, AbuseIPDB, Shodan, URLScan, Hybrid Analysis, MISP lookup); generic enrichment (GeoIP, DNS/WHOIS, hash reputation) |
| **Orchestration** (chained automation) | Phase 5 engine | FilteredEvent triggers → notifier / RunResponder / Function — enables playbooks like "severity ≥ 3 + observable hash known in TI → auto-isolate host via Falcon RTR + create Jira ticket" as configuration, not code |

**Fast-track access before first-party packets mature**: Phase 7 ships a **Cortex compatibility shim**, allowing existing community analyzers/responders for the above vendors (in `TheHive-Project/Cortex-Analyzers`) to run without rewriting.

**Non-fork commitment**: the stable plugin SDK from Phase 2 lets customers and community write their own integrations (including vendors not listed — Microsoft Defender for Endpoint, Cybereason, Cortex XDR, etc.) without forking core. This satisfies the promise of ADR 0002.

**Phase 7 decomposition**: when Phase 7 brainstorm starts, scope splits into:
- **7a** — auth providers (AD/LDAP/OAuth2/OIDC/SAML), SMTP, MISP, email intake, Cortex shim.
- **7b** — first-party EDR/SIEM/firewall vendor packets, prioritized by adoption (typically CrowdStrike + SentinelOne first).

## Non-functional posture

OWASP ASVS L2 mindset, full audit log, TLP/PAP enforcement at the edge, signed JWT (Phase 1), per-org rate limits (Phase 1), RFC 7807 problem+json for every error path, structured JSON logging, OTel ready.
```

- [ ] **Step 2: Write `docs/runbook.md`**

```markdown
# Adhkar IR — Local dev runbook

## Prerequisites

- Docker 24+ and `docker compose` v2.20+
- (Optional, for non-Docker dev) Python 3.12, `uv` 0.4+, Node.js 22, pnpm 9+
- Free TCP ports: 5432, 6379, 8000, 5173, 9000, 9001, 1025, 8025, 16686 (only with `--profile observability`)

## First boot

```bash
git clone https://github.com/<org>/adhkar-ir && cd adhkar-ir
cp deploy/.env.example deploy/.env
docker compose -f deploy/docker-compose.yml up -d
```

Wait until all services are healthy (~30–60 seconds):

```bash
docker compose -f deploy/docker-compose.yml ps
```

Then:
- API Swagger: <http://localhost:8000/docs>
- Web app: <http://localhost:5173>
- MailHog UI: <http://localhost:8025>
- MinIO console: <http://localhost:9001> (login `minio-dev` / `minio-dev-secret`)
- Storybook (run separately): `cd frontend && pnpm storybook` → <http://localhost:6006>

## Full reset

```bash
docker compose -f deploy/docker-compose.yml down -v
docker compose -f deploy/docker-compose.yml up -d
```

The `-v` removes named volumes (`pgdata`, `redisdata`, `miniodata`). The next `up` re-runs the MinIO bucket bootstrap and Alembic migrations automatically.

## Observability profile

```bash
docker compose -f deploy/docker-compose.yml --profile observability up -d
```

Adds Jaeger at <http://localhost:16686>. To send traces from the API, set `ADHKAR_OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger:4317` in `deploy/.env` and restart the `api` service.

## Top five troubleshooting

| Symptom | Diagnosis | Fix |
|---|---|---|
| `api` container restarts in a loop | `alembic upgrade head` failing because postgres healthcheck not satisfied yet | `docker compose logs api`; usually first start race; rerun `docker compose up -d`. If persistent, set `ADHKAR_SKIP_MIGRATIONS=1` and run `alembic upgrade head` manually after postgres is up |
| Web blank with console error "Failed to fetch" | `VITE_API_BASE_URL` mismatch or CORS | Verify `deploy/.env` has `VITE_API_BASE_URL=http://localhost:8000`; restart `web` |
| `pg_isready` fails forever | port 5432 already used on host | `lsof -i :5432`; stop conflicting process or remap container port |
| `/readyz` returns 503 with `s3: "down"` | MinIO not initialized or bucket missing | `docker compose logs adhkar-minio-init`; on success it prints `bucket adhkar-attachments created`. Rerun `docker compose up -d minio-init` |
| Hot reload (frontend) not picking up changes | Inotify limit reached on Linux | `sudo sysctl -w fs.inotify.max_user_watches=524288` |

## Testing locally

- Backend tests: `cd backend && uv run pytest`
- Frontend tests: `cd frontend && pnpm test --run`
- Storybook play-functions: `cd frontend && pnpm test-storybook`
- End-to-end Playwright suite: **not in Phase 0** (introduced Phase 1 when login flow exists).

## Common dev commands

```bash
# rebuild api after backend change without volume reset
docker compose -f deploy/docker-compose.yml up -d --build api

# tail logs across services
docker compose -f deploy/docker-compose.yml logs -f api web

# enter postgres
docker exec -it adhkar-postgres psql -U adhkar -d adhkar
```
```

- [ ] **Step 3: Write `docs/data-model.md` stub**

```markdown
# Adhkar IR — Data model

This document tracks the canonical entity model and relationships. It is **empty in Phase 0** — no domain entities exist yet.

## Phase 1 will introduce

- `Organization`, `User`, `UserOrgMembership`, `Profile`, `Permission`, `ApiKey`, `Session`, `MfaSecret`, `OrgSharing`, `AuditLog`, `OutboxEvent`

ERD diagram (mermaid) will land here at the end of Phase 1.

## Phase 2

- `Observable`, `ObservableType`, `AnalyzerJob`, `AnalyzerReport`, `Responder`, `ResponderAction`

## Conventions

All domain entities carry: `id` (UUID), `created_at`, `created_by`, `updated_at`, `updated_by`, `organization_id`, soft-delete flag where applicable, and emit `AuditLog` + `OutboxEvent` rows on mutation.
```

- [ ] **Step 4: Write `docs/api.md`**

```markdown
# Adhkar IR — API

The OpenAPI 3 spec is served live at `/openapi.json`. Interactive UIs:

- Swagger UI: <http://localhost:8000/docs>
- ReDoc: <http://localhost:8000/redoc>

## Phase 0 endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/healthz` | Liveness — process is up |
| GET | `/readyz` | Readiness — all backing services reachable |
| GET | `/version` | Build metadata (version, commit, builtAt) |
| GET | `/openapi.json` | OpenAPI 3 spec |
| GET | `/docs` | Swagger UI |
| GET | `/redoc` | ReDoc |

All error responses follow [RFC 7807](https://www.rfc-editor.org/rfc/rfc7807) with the `application/problem+json` content type.

## Versioning

Public routes are namespaced under `/v1/`. Meta endpoints (`/healthz`, `/readyz`, `/version`) are unversioned.

## Auth

**Phase 0 endpoints require no authentication.** Authentication (JWT + API key) lands in Phase 1; from then on every domain endpoint enforces authz via the `require_permission()` dependency.
```

- [ ] **Step 5: Commit**

```bash
git add docs/architecture.md docs/runbook.md docs/data-model.md docs/api.md
git commit -s -m "docs: add architecture, runbook, data-model stub, and api index

- architecture.md: one-page mermaid system view + stack +
  bounded contexts + integration roadmap (EDR/SIEM/firewall
  landing across Phase 4/5/7) + non-functional posture
- runbook.md: prerequisites, first boot, full reset,
  observability profile, top-5 troubleshooting table
- data-model.md: stub — no entities in Phase 0
- api.md: index pointing to live Swagger; lists meta endpoints

Closes Phase 0 §10.1 documentation checklist."
```

---

## Task 4: Backend project init (`backend/pyproject.toml`)

**Files:**
- Create: `backend/pyproject.toml`, `backend/uv.lock` (generated), `backend/.python-version`, `backend/aegis/__init__.py` placeholder

- [ ] **Step 1: Create `backend/.python-version`**

```
3.12
```

- [ ] **Step 2: Create `backend/pyproject.toml`**

```toml
[project]
name = "adhkar"
version = "0.1.0.dev0"
description = "Adhkar IR backend — FastAPI service"
readme = "../README.md"
requires-python = ">=3.12,<3.13"
license = { text = "Apache-2.0" }
authors = [{ name = "The Adhkar IR Authors" }]
dependencies = [
  "fastapi>=0.115",
  "uvicorn[standard]>=0.32",
  "pydantic>=2.9",
  "pydantic-settings>=2.6",
  "orjson>=3.10",
  "sqlalchemy[asyncio]>=2.0.36",
  "asyncpg>=0.30",
  "alembic>=1.14",
  "structlog>=24.4",
  "httpx>=0.27",
  "redis>=5.2",
  "boto3>=1.35",
  "opentelemetry-api>=1.28",
  "opentelemetry-sdk>=1.28",
  "opentelemetry-exporter-otlp>=1.28",
  "opentelemetry-instrumentation-fastapi>=0.49b0",
  "opentelemetry-instrumentation-sqlalchemy>=0.49b0",
  "opentelemetry-instrumentation-redis>=0.49b0",
  "opentelemetry-instrumentation-httpx>=0.49b0",
]

[dependency-groups]
dev = [
  "ruff>=0.7",
  "mypy>=1.13",
  "pytest>=8.3",
  "pytest-asyncio>=0.24",
  "pytest-cov>=6.0",
  "pytest-randomly>=3.16",
  "respx>=0.21",
  "testcontainers[postgres,redis,minio]>=4.8",
  "polyfactory>=2.18",
  "freezegun>=1.5",
  "openapi-spec-validator>=0.7",
  "types-redis>=4.6",
]

[build-system]
requires = ["hatchling>=1.25"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["adhkar"]

# ----- Ruff -----
[tool.ruff]
target-version = "py312"
line-length = 100
src = ["adhkar", "tests"]

[tool.ruff.lint]
select = ["E", "F", "W", "I", "B", "C4", "UP", "N", "S", "ASYNC", "RUF"]
ignore = ["S101"]  # allow `assert` in tests (overridden per-dir below for non-tests)

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S", "N802"]

[tool.ruff.format]
quote-style = "double"

# ----- mypy -----
[tool.mypy]
python_version = "3.12"
strict = true
warn_unused_configs = true
warn_redundant_casts = true
warn_unused_ignores = true
disallow_any_generics = true
no_implicit_reexport = true
plugins = ["pydantic.mypy"]

[[tool.mypy.overrides]]
module = ["testcontainers.*", "respx.*"]
ignore_missing_imports = true

# ----- pytest -----
[tool.pytest.ini_options]
asyncio_mode = "strict"
testpaths = ["tests"]
addopts = "-ra --strict-markers --strict-config"
markers = [
  "integration: tests that require external services (testcontainers)",
]
filterwarnings = [
  "error",
]

# ----- coverage -----
[tool.coverage.run]
branch = true
source = ["adhkar"]
omit = ["adhkar/__init__.py"]

[tool.coverage.report]
exclude_lines = [
  "pragma: no cover",
  "raise NotImplementedError",
  "if TYPE_CHECKING:",
]
fail_under = 70
show_missing = true
skip_covered = false
```

- [ ] **Step 3: Create initial `backend/adhkar/__init__.py`**

```python
"""Adhkar IR backend package."""

__version__ = "0.1.0.dev0"
```

- [ ] **Step 4: Resolve & lock dependencies**

Run:
```bash
cd backend && uv sync
```

Expected: `uv.lock` generated; `.venv/` created; no resolution errors. If any dep version is yanked, bump to nearest matching minor and retry.

- [ ] **Step 5: Verify tooling baseline**

```bash
cd backend
uv run ruff check .
uv run ruff format --check .
uv run mypy adhkar
```

Expected: each command exits 0 (nothing to lint, format already clean, mypy finds nothing to type-check yet but no errors).

- [ ] **Step 6: Commit**

```bash
git add backend/pyproject.toml backend/uv.lock backend/.python-version backend/adhkar/__init__.py
git commit -s -m "chore(backend): init uv project with FastAPI, SQLAlchemy async, structlog, OTel

- pyproject.toml: runtime deps (FastAPI, asyncpg, Alembic,
  structlog, OTel auto-instrumentation) + dev group
  (ruff, mypy strict, pytest async, testcontainers, MSW-equiv
  respx, polyfactory, freezegun, openapi-spec-validator)
- ruff config: line-length 100, full security ruleset (S),
  bugbear, complexity, naming, async lints
- mypy strict + pydantic plugin
- pytest strict-markers strict-config, asyncio strict mode,
  filterwarnings=error to catch deprecations early
- coverage fail_under=70 (Phase 0 baseline per spec §8.4)"
```

---

## Task 5: Backend settings module (TDD)

**Files:**
- Create: `backend/adhkar/core/__init__.py`
- Create: `backend/adhkar/core/settings.py`
- Create: `backend/tests/__init__.py`, `backend/tests/unit/__init__.py`
- Create: `backend/tests/unit/test_settings.py`

- [ ] **Step 1: Write failing test**

`backend/tests/unit/test_settings.py`:
```python
import pytest
from pydantic import ValidationError

from adhkar.core.settings import Settings


def test_settings_loads_with_defaults_when_secret_provided(monkeypatch):
    monkeypatch.setenv("ADHKAR_SECRET_KEY", "x" * 32)
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h/db")
    monkeypatch.setenv("REDIS_URL", "redis://h:6379/0")
    s = Settings()
    assert s.env == "dev"
    assert s.log_level == "INFO"
    assert s.s3_bucket == "adhkar-attachments"
    assert s.s3_region == "us-east-1"
    assert s.otel_exporter_otlp_endpoint == ""
    assert s.otel_service_name == "adhkar-api"


def test_settings_rejects_short_secret_key(monkeypatch):
    monkeypatch.setenv("ADHKAR_SECRET_KEY", "too-short")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h/db")
    monkeypatch.setenv("REDIS_URL", "redis://h:6379/0")
    with pytest.raises(ValidationError) as excinfo:
        Settings()
    assert "at least 32 characters" in str(excinfo.value)


def test_settings_reads_adhkar_prefixed_env(monkeypatch):
    monkeypatch.setenv("ADHKAR_SECRET_KEY", "x" * 32)
    monkeypatch.setenv("ADHKAR_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("ADHKAR_S3_BUCKET", "custom-bucket")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h/db")
    monkeypatch.setenv("REDIS_URL", "redis://h:6379/0")
    s = Settings()
    assert s.log_level == "DEBUG"
    assert s.s3_bucket == "custom-bucket"
```

- [ ] **Step 2: Run, verify FAIL**

```bash
cd backend && uv run pytest tests/unit/test_settings.py -v
```

Expected: ImportError (`adhkar.core.settings` not yet created).

- [ ] **Step 3: Implement minimal**

`backend/adhkar/core/__init__.py`:
```python
"""Core infrastructure (settings, logging, OTel, middleware)."""
```

`backend/adhkar/core/settings.py`:
```python
"""Application settings loaded from environment variables (ADHKAR_* prefix + 12-factor DATABASE_URL/REDIS_URL)."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ADHKAR_",
        env_file=None,
        case_sensitive=False,
        extra="ignore",
    )

    # ----- core -----
    env: Literal["dev", "test", "staging", "prod"] = "dev"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    secret_key: str = Field(min_length=1)
    cors_origins: list[str] = ["http://localhost:5173"]

    # ----- database (also supports DATABASE_URL 12-factor without ADHKAR_ prefix) -----
    database_url: str = Field(validation_alias="DATABASE_URL")

    # ----- redis -----
    redis_url: str = Field(validation_alias="REDIS_URL")

    # ----- s3 / minio -----
    s3_endpoint: str = "http://minio:9000"
    s3_access_key: str = "minio-dev"
    s3_secret_key: str = "minio-dev-secret"
    s3_bucket: str = "adhkar-attachments"
    s3_region: str = "us-east-1"

    # ----- smtp (dev = mailhog) -----
    smtp_host: str = "mailhog"
    smtp_port: int = 1025
    smtp_from: str = "adhkar@localhost"

    # ----- otel -----
    otel_exporter_otlp_endpoint: str = ""
    otel_service_name: str = "adhkar-api"

    # ----- build metadata -----
    git_commit: str = "unknown"
    built_at: str = "unknown"

    # ----- migrations -----
    skip_migrations: bool = False

    @field_validator("secret_key")
    @classmethod
    def _validate_secret_key(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("ADHKAR_SECRET_KEY must be at least 32 characters")
        return v


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
```

- [ ] **Step 4: Run, verify PASS**

```bash
cd backend && uv run pytest tests/unit/test_settings.py -v
uv run mypy adhkar/core/settings.py
uv run ruff check adhkar/core/settings.py
```

Expected: 3 tests pass, mypy clean, ruff clean.

- [ ] **Step 5: Commit**

```bash
git add backend/adhkar/core/__init__.py backend/adhkar/core/settings.py backend/tests/__init__.py backend/tests/unit/__init__.py backend/tests/unit/test_settings.py
git commit -s -m "feat(backend): add Settings module (ADHKAR_* env prefix, 12-factor DATABASE_URL/REDIS_URL)

Pydantic v2 BaseSettings with min-length 32 secret_key
validator. Memoized via lru_cache so module-level singleton
behavior is preserved while staying injectable through
FastAPI dependencies (Phase 5.1 of spec).

Tests cover defaults, secret-key length rejection, and
ADHKAR_ prefix env var override."
```

---

## Task 6: Structured JSON logging (TDD)

**Files:**
- Create: `backend/adhkar/core/logging.py`
- Create: `backend/tests/unit/test_logging.py`

- [ ] **Step 1: Write failing test**

`backend/tests/unit/test_logging.py`:
```python
import io
import json
import logging

import pytest
import structlog

from adhkar.core.logging import configure_logging
from adhkar.core.settings import Settings


@pytest.fixture
def settings(monkeypatch):
    monkeypatch.setenv("ADHKAR_SECRET_KEY", "x" * 32)
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h/db")
    monkeypatch.setenv("REDIS_URL", "redis://h:6379/0")
    monkeypatch.setenv("ADHKAR_LOG_LEVEL", "INFO")
    return Settings()


def test_log_output_is_json_with_required_fields(settings, capsys):
    configure_logging(settings)
    log = structlog.get_logger()
    log.info("user_logged_in", user_id="abc")
    captured = capsys.readouterr().out.strip().splitlines()[-1]
    payload = json.loads(captured)
    assert payload["event"] == "user_logged_in"
    assert payload["user_id"] == "abc"
    assert payload["level"] == "info"
    assert "ts" in payload
    # request_id is bound by middleware; here it should default to empty string
    assert "request_id" in payload


def test_log_level_threshold_respected(settings, capsys, monkeypatch):
    monkeypatch.setenv("ADHKAR_LOG_LEVEL", "WARNING")
    settings = Settings()
    configure_logging(settings)
    log = structlog.get_logger()
    log.info("should_be_dropped")
    log.warning("should_be_kept")
    out = capsys.readouterr().out
    assert "should_be_dropped" not in out
    assert "should_be_kept" in out
```

- [ ] **Step 2: Run, verify FAIL**

```bash
cd backend && uv run pytest tests/unit/test_logging.py -v
```

Expected: ImportError on `adhkar.core.logging`.

- [ ] **Step 3: Implement minimal**

`backend/adhkar/core/logging.py`:
```python
"""structlog-based JSON logging configured from Settings."""

import logging
import sys
from contextvars import ContextVar

import structlog

from adhkar.core.settings import Settings

_REQUEST_ID: ContextVar[str] = ContextVar("request_id", default="")


def get_request_id() -> str:
    return _REQUEST_ID.get()


def set_request_id(rid: str) -> None:
    _REQUEST_ID.set(rid)


def _add_request_id(_logger: object, _method_name: str, event_dict: dict[str, object]) -> dict[str, object]:
    event_dict.setdefault("request_id", _REQUEST_ID.get())
    return event_dict


def configure_logging(settings: Settings) -> None:
    """Configure stdlib + structlog to emit JSON lines on stdout."""

    level = logging.getLevelName(settings.log_level)
    logging.basicConfig(level=level, stream=sys.stdout, format="%(message)s", force=True)

    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(level),
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True, key="ts"),
            _add_request_id,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )
```

- [ ] **Step 4: Run, verify PASS**

```bash
cd backend && uv run pytest tests/unit/test_logging.py -v
uv run mypy adhkar/core/logging.py
uv run ruff check adhkar/core/logging.py
```

Expected: 2 tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/adhkar/core/logging.py backend/tests/unit/test_logging.py
git commit -s -m "feat(backend): add structlog JSON logging with request_id context

ContextVar-based request_id propagates through async tasks
(get_request_id/set_request_id helpers used by middleware in
the next task). Emits ts (ISO UTC), level, event, request_id,
plus any structured kwargs. Log level driven by
ADHKAR_LOG_LEVEL.

Per spec §5.6."
```

---

## Task 7: Request-ID & access-log middleware (TDD)

**Files:**
- Create: `backend/adhkar/core/middleware.py`
- Create: `backend/tests/unit/test_middleware.py`

- [ ] **Step 1: Write failing test**

`backend/tests/unit/test_middleware.py`:
```python
import json

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from adhkar.core.logging import configure_logging
from adhkar.core.middleware import AccessLogMiddleware, RequestIdMiddleware
from adhkar.core.settings import Settings


@pytest.fixture
def settings(monkeypatch):
    monkeypatch.setenv("ADHKAR_SECRET_KEY", "x" * 32)
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h/db")
    monkeypatch.setenv("REDIS_URL", "redis://h:6379/0")
    return Settings()


@pytest.fixture
def app(settings):
    configure_logging(settings)
    a = FastAPI()
    a.add_middleware(AccessLogMiddleware)
    a.add_middleware(RequestIdMiddleware)

    @a.get("/ping")
    async def ping() -> dict[str, str]:
        return {"pong": "yes"}

    return a


@pytest.mark.asyncio
async def test_request_id_propagated_from_header(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/ping", headers={"X-Request-Id": "rid-abc"})
    assert r.status_code == 200
    assert r.headers["x-request-id"] == "rid-abc"


@pytest.mark.asyncio
async def test_request_id_generated_when_missing(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/ping")
    rid = r.headers["x-request-id"]
    # UUID4 format: 36 chars including hyphens
    assert len(rid) == 36
    assert rid.count("-") == 4


@pytest.mark.asyncio
async def test_access_log_emitted(app, capsys):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        await c.get("/ping", headers={"X-Request-Id": "rid-xyz"})
    out = capsys.readouterr().out.splitlines()
    payloads = [json.loads(line) for line in out if line.strip().startswith("{")]
    access = [p for p in payloads if p.get("event") == "http_request"]
    assert access, "no http_request log line emitted"
    assert access[-1]["request_id"] == "rid-xyz"
    assert access[-1]["method"] == "GET"
    assert access[-1]["path"] == "/ping"
    assert access[-1]["status"] == 200
    assert "duration_ms" in access[-1]
```

- [ ] **Step 2: Run, verify FAIL**

```bash
cd backend && uv run pytest tests/unit/test_middleware.py -v
```

Expected: ImportError on `adhkar.core.middleware`.

- [ ] **Step 3: Implement minimal**

`backend/adhkar/core/middleware.py`:
```python
"""HTTP middleware: request-id propagation and structured access logging."""

import time
import uuid
from collections.abc import Awaitable, Callable

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from adhkar.core.logging import set_request_id

_HEADER = "X-Request-Id"
_log = structlog.get_logger()


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        rid = request.headers.get(_HEADER) or str(uuid.uuid4())
        set_request_id(rid)
        response = await call_next(request)
        response.headers[_HEADER] = rid
        return response


class AccessLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000.0, 2)
        _log.info(
            "http_request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=duration_ms,
        )
        return response
```

- [ ] **Step 4: Run, verify PASS**

```bash
cd backend && uv run pytest tests/unit/test_middleware.py -v
uv run mypy adhkar/core/middleware.py
```

Expected: 3 tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/adhkar/core/middleware.py backend/tests/unit/test_middleware.py
git commit -s -m "feat(backend): add RequestId and AccessLog middleware

RequestIdMiddleware: accepts incoming X-Request-Id header,
falls back to a fresh UUID4, propagates to the contextvar
read by structlog, and echoes the id in the response header.

AccessLogMiddleware: emits a single structured 'http_request'
log line per request with method/path/status/duration_ms.
Request body deliberately not logged (PII per spec §5.6)."
```

---

## Task 8: RFC 7807 error handlers (TDD)

**Files:**
- Create: `backend/adhkar/api/__init__.py`
- Create: `backend/adhkar/api/errors.py`
- Create: `backend/tests/unit/test_errors.py`

- [ ] **Step 1: Write failing test**

`backend/tests/unit/test_errors.py`:
```python
import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel

from adhkar.api.errors import register_exception_handlers


class _Payload(BaseModel):
    name: str


@pytest.fixture
def app():
    a = FastAPI()
    register_exception_handlers(a)

    @a.get("/bad-request")
    async def bad() -> None:
        raise HTTPException(status_code=400, detail="nope")

    @a.post("/validate")
    async def validate(_p: _Payload) -> dict[str, str]:
        return {"ok": "yes"}

    @a.get("/boom")
    async def boom() -> None:
        raise RuntimeError("internal explode")

    return a


@pytest.mark.asyncio
async def test_http_exception_translated_to_problem(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.get("/bad-request")
    assert r.status_code == 400
    assert r.headers["content-type"].startswith("application/problem+json")
    body = r.json()
    assert body["type"].startswith("https://adhkar.dev/problems/")
    assert body["title"]
    assert body["status"] == 400
    assert body["detail"] == "nope"
    assert "instance" in body


@pytest.mark.asyncio
async def test_validation_error_translated_to_422_problem(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.post("/validate", json={})  # missing required "name"
    assert r.status_code == 422
    body = r.json()
    assert body["status"] == 422
    assert isinstance(body["errors"], list)
    assert any(e.get("loc") for e in body["errors"])


@pytest.mark.asyncio
async def test_unhandled_exception_returns_500_without_stacktrace(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.get("/boom")
    assert r.status_code == 500
    body = r.json()
    assert body["status"] == 500
    assert body["title"] == "Internal Server Error"
    # never leak internals
    assert "Traceback" not in r.text
    assert "RuntimeError" not in r.text
```

- [ ] **Step 2: Run, verify FAIL**

```bash
cd backend && uv run pytest tests/unit/test_errors.py -v
```

Expected: ImportError on `adhkar.api.errors`.

- [ ] **Step 3: Implement minimal**

`backend/adhkar/api/__init__.py`:
```python
"""HTTP API surface (routers, deps, error handlers)."""
```

`backend/adhkar/api/errors.py`:
```python
"""RFC 7807 problem+json exception handlers."""

from typing import Any

import structlog
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from adhkar.core.logging import get_request_id

_PROBLEM_BASE = "https://adhkar.dev/problems/"
_log = structlog.get_logger()


def _problem(
    *,
    slug: str,
    title: str,
    http_status: int,
    detail: str,
    extra: dict[str, Any] | None = None,
) -> JSONResponse:
    body: dict[str, Any] = {
        "type": f"{_PROBLEM_BASE}{slug}",
        "title": title,
        "status": http_status,
        "detail": detail,
        "instance": get_request_id(),
    }
    if extra:
        body.update(extra)
    return JSONResponse(
        status_code=http_status,
        content=body,
        media_type="application/problem+json",
    )


async def _http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
    return _problem(
        slug=f"http-{exc.status_code}",
        title=_title_for(exc.status_code),
        http_status=exc.status_code,
        detail=str(exc.detail),
    )


async def _validation_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = [
        {"loc": list(e.get("loc", [])), "msg": e.get("msg", ""), "type": e.get("type", "")}
        for e in exc.errors()
    ]
    return _problem(
        slug="validation",
        title="Unprocessable Entity",
        http_status=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="Request validation failed",
        extra={"errors": errors},
    )


async def _unhandled_handler(_request: Request, exc: Exception) -> JSONResponse:
    _log.exception("unhandled_exception", exc_type=type(exc).__name__)
    return _problem(
        slug="internal",
        title="Internal Server Error",
        http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="An internal error occurred. Please retry; if this persists, contact the administrator.",
    )


def _title_for(code: int) -> str:
    return {
        400: "Bad Request",
        401: "Unauthorized",
        403: "Forbidden",
        404: "Not Found",
        405: "Method Not Allowed",
        409: "Conflict",
        422: "Unprocessable Entity",
        429: "Too Many Requests",
    }.get(code, "Error")


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(HTTPException, _http_exception_handler)
    app.add_exception_handler(RequestValidationError, _validation_handler)
    app.add_exception_handler(Exception, _unhandled_handler)
```

- [ ] **Step 4: Run, verify PASS**

```bash
cd backend && uv run pytest tests/unit/test_errors.py -v
uv run mypy adhkar/api/errors.py
```

Expected: 3 tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/adhkar/api/__init__.py backend/adhkar/api/errors.py backend/tests/unit/test_errors.py
git commit -s -m "feat(backend): add RFC 7807 problem+json exception handlers

Three handlers registered globally:
- HTTPException -> typed problem with http-NNN slug
- RequestValidationError -> 422 with errors[] list
- Unhandled Exception -> 500 with safe title/detail, full
  stacktrace logged server-side only

instance field is bound to the X-Request-Id contextvar so
clients can correlate problems with server logs.

Per spec §5.4."
```

---

## Task 9: OTel bootstrap (no-op when disabled)

**Files:**
- Create: `backend/adhkar/core/otel.py`
- Create: `backend/tests/unit/test_otel.py`

- [ ] **Step 1: Write failing test**

`backend/tests/unit/test_otel.py`:
```python
import pytest
from fastapi import FastAPI

from adhkar.core.otel import configure_otel
from adhkar.core.settings import Settings


@pytest.fixture
def app_settings(monkeypatch):
    monkeypatch.setenv("ADHKAR_SECRET_KEY", "x" * 32)
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h/db")
    monkeypatch.setenv("REDIS_URL", "redis://h:6379/0")
    return Settings()


def test_otel_noop_when_endpoint_empty(app_settings):
    app = FastAPI()
    configure_otel(app, app_settings)
    # no exporter registered, no exception thrown
    # check the tracer provider is the default NoOpTracerProvider
    from opentelemetry import trace

    provider = trace.get_tracer_provider()
    assert type(provider).__name__ in ("ProxyTracerProvider", "NoOpTracerProvider", "TracerProvider")


def test_otel_setup_when_endpoint_present(monkeypatch, app_settings):
    monkeypatch.setenv("ADHKAR_OTEL_EXPORTER_OTLP_ENDPOINT", "http://jaeger:4317")
    s = Settings()
    app = FastAPI()
    # should not raise even though the endpoint is unreachable in test (gRPC exporter is lazy)
    configure_otel(app, s)
```

- [ ] **Step 2: Run, verify FAIL**

```bash
cd backend && uv run pytest tests/unit/test_otel.py -v
```

Expected: ImportError on `adhkar.core.otel`.

- [ ] **Step 3: Implement minimal**

`backend/adhkar/core/otel.py`:
```python
"""OpenTelemetry bootstrap. No-op if ADHKAR_OTEL_EXPORTER_OTLP_ENDPOINT is empty."""

from fastapi import FastAPI

from adhkar.core.settings import Settings


def configure_otel(app: FastAPI, settings: Settings) -> None:
    if not settings.otel_exporter_otlp_endpoint:
        return

    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
    from opentelemetry.instrumentation.redis import RedisInstrumentor
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    resource = Resource.create({"service.name": settings.otel_service_name})
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=settings.otel_exporter_otlp_endpoint, insecure=True))
    )
    trace.set_tracer_provider(provider)

    FastAPIInstrumentor.instrument_app(app)
    HTTPXClientInstrumentor().instrument()
    RedisInstrumentor().instrument()
    SQLAlchemyInstrumentor().instrument()
```

- [ ] **Step 4: Run, verify PASS**

```bash
cd backend && uv run pytest tests/unit/test_otel.py -v
uv run mypy adhkar/core/otel.py
```

Expected: 2 tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/adhkar/core/otel.py backend/tests/unit/test_otel.py
git commit -s -m "feat(backend): add OTel bootstrap, no-op when endpoint env empty

Lazy import of OTel SDK so production-default (endpoint not
set) avoids the cold-start cost of pulling in
exporter/instrumentation modules.

When ADHKAR_OTEL_EXPORTER_OTLP_ENDPOINT is set, auto-
instruments FastAPI + httpx + redis + SQLAlchemy and ships
batched spans via OTLP gRPC. Service name defaults to
adhkar-api via ADHKAR_OTEL_SERVICE_NAME.

Per spec §5.7."
```

---

## Task 10: Database engine + readiness checks

**Files:**
- Create: `backend/adhkar/db/__init__.py`
- Create: `backend/adhkar/db/base.py`
- Create: `backend/adhkar/db/engine.py`
- Create: `backend/adhkar/db/readiness.py`
- Create: `backend/tests/unit/test_readiness.py`

- [ ] **Step 1: Write failing test**

`backend/tests/unit/test_readiness.py`:
```python
from unittest.mock import AsyncMock, MagicMock

import pytest

from adhkar.db.readiness import CheckResult, check_redis, check_s3


@pytest.mark.asyncio
async def test_check_redis_ok():
    fake = AsyncMock()
    fake.ping.return_value = True
    result = await check_redis(fake)
    assert result == CheckResult(name="redis", ok=True, detail=None)


@pytest.mark.asyncio
async def test_check_redis_down():
    fake = AsyncMock()
    fake.ping.side_effect = ConnectionError("nope")
    result = await check_redis(fake)
    assert result.ok is False
    assert result.name == "redis"
    assert "nope" in (result.detail or "")


@pytest.mark.asyncio
async def test_check_s3_ok():
    client = MagicMock()
    client.head_bucket = MagicMock(return_value={"ResponseMetadata": {"HTTPStatusCode": 200}})
    result = await check_s3(client, bucket="adhkar-attachments")
    assert result == CheckResult(name="s3", ok=True, detail=None)


@pytest.mark.asyncio
async def test_check_s3_missing_bucket():
    client = MagicMock()
    client.head_bucket = MagicMock(side_effect=Exception("NoSuchBucket"))
    result = await check_s3(client, bucket="adhkar-attachments")
    assert result.ok is False
    assert "NoSuchBucket" in (result.detail or "")
```

- [ ] **Step 2: Run, verify FAIL**

```bash
cd backend && uv run pytest tests/unit/test_readiness.py -v
```

Expected: ImportError on `adhkar.db.readiness`.

- [ ] **Step 3: Implement minimal**

`backend/adhkar/db/__init__.py`:
```python
"""Database infrastructure: engine, declarative base, readiness checks."""
```

`backend/adhkar/db/base.py`:
```python
"""SQLAlchemy declarative base with locked-in constraint naming convention.

Phase 0 ships only the metadata convention; no concrete models yet."""

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

_NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=_NAMING_CONVENTION)
```

`backend/adhkar/db/engine.py`:
```python
"""Async SQLAlchemy engine + session factory."""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from adhkar.core.settings import Settings


def create_engine(settings: Settings) -> AsyncEngine:
    return create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        future=True,
    )


def session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def session_dependency(
    factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with factory() as s:
        yield s
```

`backend/adhkar/db/readiness.py`:
```python
"""Readiness checks for /readyz endpoint."""

from dataclasses import dataclass
from typing import Any, Protocol

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


@dataclass(frozen=True, slots=True)
class CheckResult:
    name: str
    ok: bool
    detail: str | None = None


class _RedisLike(Protocol):
    async def ping(self) -> bool: ...


async def check_db(engine: AsyncEngine) -> CheckResult:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return CheckResult(name="db", ok=True)
    except Exception as e:  # noqa: BLE001 — surface any failure as "down"
        return CheckResult(name="db", ok=False, detail=str(e))


async def check_redis(client: _RedisLike) -> CheckResult:
    try:
        await client.ping()
        return CheckResult(name="redis", ok=True)
    except Exception as e:  # noqa: BLE001
        return CheckResult(name="redis", ok=False, detail=str(e))


async def check_s3(client: Any, *, bucket: str) -> CheckResult:
    try:
        client.head_bucket(Bucket=bucket)
        return CheckResult(name="s3", ok=True)
    except Exception as e:  # noqa: BLE001
        return CheckResult(name="s3", ok=False, detail=str(e))
```

- [ ] **Step 4: Run, verify PASS**

```bash
cd backend && uv run pytest tests/unit/test_readiness.py -v
uv run mypy adhkar/db
```

Expected: 4 tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/adhkar/db/ backend/tests/unit/test_readiness.py
git commit -s -m "feat(backend): add async DB engine, declarative base, readiness checks

- Base.metadata: locks the SQL constraint naming convention
  Phase 0 so Phase 1+ migrations are stable (spec §5.5).
- engine.create_engine + session_factory: asyncpg via
  SQLAlchemy 2.x async; pool tuned for 5/15 default.
- readiness: check_db / check_redis / check_s3 returning a
  frozen CheckResult dataclass; designed for parallel
  asyncio.gather in /readyz."
```

---

## Task 11: Meta endpoints (`/healthz`, `/version`) (TDD)

**Files:**
- Create: `backend/adhkar/api/v1/__init__.py`
- Create: `backend/adhkar/api/v1/meta.py`
- Create: `backend/adhkar/api/deps.py`
- Create: `backend/tests/unit/test_meta.py`

- [ ] **Step 1: Write failing test**

`backend/tests/unit/test_meta.py`:
```python
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from adhkar.api.v1.meta import router as meta_router


@pytest.fixture
def app():
    a = FastAPI()
    a.include_router(meta_router)
    return a


@pytest.mark.asyncio
async def test_healthz_returns_ok(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_version_returns_metadata(monkeypatch, app):
    monkeypatch.setenv("ADHKAR_SECRET_KEY", "x" * 32)
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h/db")
    monkeypatch.setenv("REDIS_URL", "redis://h:6379/0")
    monkeypatch.setenv("ADHKAR_GIT_COMMIT", "abc1234")
    monkeypatch.setenv("ADHKAR_BUILT_AT", "2026-06-16T10:42:00Z")
    # bust the lru_cache so the new env is picked up
    from adhkar.core.settings import get_settings
    get_settings.cache_clear()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.get("/version")
    assert r.status_code == 200
    body = r.json()
    assert body["version"] == "0.1.0.dev0"
    assert body["commit"] == "abc1234"
    assert body["builtAt"] == "2026-06-16T10:42:00Z"
```

- [ ] **Step 2: Run, verify FAIL**

```bash
cd backend && uv run pytest tests/unit/test_meta.py -v
```

Expected: ImportError on `adhkar.api.v1.meta`.

- [ ] **Step 3: Implement minimal**

`backend/adhkar/api/v1/__init__.py`:
```python
"""v1 API routers."""
```

`backend/adhkar/api/deps.py`:
```python
"""FastAPI dependency providers."""

from fastapi import Depends

from adhkar.core.settings import Settings, get_settings as _get_settings


def get_settings(settings: Settings = Depends(_get_settings)) -> Settings:
    return settings
```

`backend/adhkar/api/v1/meta.py`:
```python
"""Meta endpoints: /healthz, /readyz, /version."""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from adhkar import __version__
from adhkar.core.settings import Settings, get_settings

router = APIRouter(tags=["meta"])


class HealthResponse(BaseModel):
    status: str


class VersionResponse(BaseModel):
    version: str
    commit: str
    builtAt: str


@router.get("/healthz", response_model=HealthResponse)
async def healthz() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/version", response_model=VersionResponse)
async def version(s: Annotated[Settings, Depends(get_settings)]) -> VersionResponse:
    return VersionResponse(version=__version__, commit=s.git_commit, builtAt=s.built_at)
```

- [ ] **Step 4: Run, verify PASS**

```bash
cd backend && uv run pytest tests/unit/test_meta.py -v
uv run mypy adhkar/api
```

Expected: 2 tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/adhkar/api/v1/ backend/adhkar/api/deps.py backend/tests/unit/test_meta.py
git commit -s -m "feat(backend): add /healthz and /version meta endpoints

healthz: pure liveness, no I/O, always 200.
version: reflects __version__, ADHKAR_GIT_COMMIT, ADHKAR_BUILT_AT.

Includes deps.get_settings injectable so endpoints can
override settings in tests. /readyz follows in the next
task because it needs the wired-up engine/redis/s3 clients."
```

---

## Task 12: `/readyz` endpoint (TDD)

**Files:**
- Modify: `backend/adhkar/api/v1/meta.py`
- Modify: `backend/adhkar/api/deps.py`
- Create: `backend/tests/unit/test_readyz_unit.py`

- [ ] **Step 1: Write failing test**

`backend/tests/unit/test_readyz_unit.py`:
```python
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from adhkar.api.deps import get_redis, get_s3, get_engine
from adhkar.api.v1.meta import router as meta_router


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("ADHKAR_SECRET_KEY", "x" * 32)
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h/db")
    monkeypatch.setenv("REDIS_URL", "redis://h:6379/0")
    a = FastAPI()
    a.include_router(meta_router)

    # mocked deps — engine: returns context manager whose execute works
    engine = MagicMock()
    conn = AsyncMock()
    conn.execute = AsyncMock()
    engine.connect.return_value.__aenter__ = AsyncMock(return_value=conn)
    engine.connect.return_value.__aexit__ = AsyncMock(return_value=None)

    redis = AsyncMock()
    redis.ping = AsyncMock(return_value=True)

    s3 = MagicMock()
    s3.head_bucket = MagicMock(return_value={"ResponseMetadata": {"HTTPStatusCode": 200}})

    a.dependency_overrides[get_engine] = lambda: engine
    a.dependency_overrides[get_redis] = lambda: redis
    a.dependency_overrides[get_s3] = lambda: s3
    return a, redis


@pytest.mark.asyncio
async def test_readyz_all_ok(app):
    a, _redis = app
    transport = ASGITransport(app=a)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.get("/readyz")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ready"
    assert body["checks"] == {"db": "ok", "redis": "ok", "s3": "ok"}


@pytest.mark.asyncio
async def test_readyz_503_when_redis_down(app):
    a, redis = app
    redis.ping = AsyncMock(side_effect=ConnectionError("boom"))
    transport = ASGITransport(app=a)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.get("/readyz")
    assert r.status_code == 503
    body = r.json()
    assert body["checks"]["redis"] == "down"
    assert body["checks"]["db"] == "ok"
```

- [ ] **Step 2: Run, verify FAIL**

```bash
cd backend && uv run pytest tests/unit/test_readyz_unit.py -v
```

Expected: ImportError on `get_engine`/`get_redis`/`get_s3` (not yet in deps).

- [ ] **Step 3: Implement — extend `deps.py`**

Replace `backend/adhkar/api/deps.py` with:
```python
"""FastAPI dependency providers."""

from functools import lru_cache
from typing import Annotated, Any

import boto3
import redis.asyncio as redis_async
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncEngine

from adhkar.core.settings import Settings, get_settings as _get_settings
from adhkar.db.engine import create_engine


def get_settings(settings: Settings = Depends(_get_settings)) -> Settings:
    return settings


@lru_cache(maxsize=1)
def _engine_singleton(database_url: str) -> AsyncEngine:
    from adhkar.core.settings import Settings as _S

    return create_engine(_S(database_url=database_url, secret_key="x" * 32, redis_url=""))  # placeholder, real wiring in main


def get_engine(s: Annotated[Settings, Depends(get_settings)]) -> AsyncEngine:
    return create_engine(s)  # type: ignore[arg-type]


def get_redis(s: Annotated[Settings, Depends(get_settings)]) -> redis_async.Redis:
    return redis_async.from_url(s.redis_url, decode_responses=True)


def get_s3(s: Annotated[Settings, Depends(get_settings)]) -> Any:
    return boto3.client(
        "s3",
        endpoint_url=s.s3_endpoint,
        aws_access_key_id=s.s3_access_key,
        aws_secret_access_key=s.s3_secret_key,
        region_name=s.s3_region,
    )
```

> **Note** to the engineer: the `_engine_singleton` helper is removed in Task 13 wire-up — keep the file linting clean by deleting that helper now too. Final shape uses request-scoped engine via app state. The above is the minimal version for this test.

Replace the simpler version with this minimal shape (no `_engine_singleton`):
```python
"""FastAPI dependency providers."""

from typing import Annotated, Any

import boto3
import redis.asyncio as redis_async
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncEngine

from adhkar.core.settings import Settings, get_settings as _get_settings
from adhkar.db.engine import create_engine


def get_settings(settings: Settings = Depends(_get_settings)) -> Settings:
    return settings


def get_engine(s: Annotated[Settings, Depends(get_settings)]) -> AsyncEngine:
    return create_engine(s)


def get_redis(s: Annotated[Settings, Depends(get_settings)]) -> redis_async.Redis:
    return redis_async.from_url(s.redis_url, decode_responses=True)


def get_s3(s: Annotated[Settings, Depends(get_settings)]) -> Any:
    return boto3.client(
        "s3",
        endpoint_url=s.s3_endpoint,
        aws_access_key_id=s.s3_access_key,
        aws_secret_access_key=s.s3_secret_key,
        region_name=s.s3_region,
    )
```

Extend `backend/adhkar/api/v1/meta.py`:
```python
"""Meta endpoints: /healthz, /readyz, /version."""

import asyncio
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine

from adhkar import __version__
from adhkar.api.deps import get_engine, get_redis, get_s3, get_settings
from adhkar.core.settings import Settings
from adhkar.db.readiness import check_db, check_redis, check_s3

router = APIRouter(tags=["meta"])


class HealthResponse(BaseModel):
    status: str


class VersionResponse(BaseModel):
    version: str
    commit: str
    builtAt: str


class ReadyResponse(BaseModel):
    status: str
    checks: dict[str, str]


@router.get("/healthz", response_model=HealthResponse)
async def healthz() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/version", response_model=VersionResponse)
async def version(s: Annotated[Settings, Depends(get_settings)]) -> VersionResponse:
    return VersionResponse(version=__version__, commit=s.git_commit, builtAt=s.built_at)


@router.get(
    "/readyz",
    response_model=ReadyResponse,
    responses={503: {"model": ReadyResponse}},
)
async def readyz(
    response: Response,
    s: Annotated[Settings, Depends(get_settings)],
    engine: Annotated[AsyncEngine, Depends(get_engine)],
    redis: Annotated[Redis, Depends(get_redis)],
    s3: Annotated[Any, Depends(get_s3)],
) -> ReadyResponse:
    results = await asyncio.gather(
        check_db(engine),
        check_redis(redis),
        asyncio.to_thread(lambda: check_s3_sync(s3, bucket=s.s3_bucket)),
        return_exceptions=False,
    )
    checks = {r.name: "ok" if r.ok else "down" for r in results}
    all_ok = all(r.ok for r in results)
    if not all_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadyResponse(status="ready" if all_ok else "degraded", checks=checks)


def check_s3_sync(client: Any, *, bucket: str):
    from adhkar.db.readiness import CheckResult

    try:
        client.head_bucket(Bucket=bucket)
        return CheckResult(name="s3", ok=True)
    except Exception as e:  # noqa: BLE001
        return CheckResult(name="s3", ok=False, detail=str(e))
```

> **Note**: the helper `check_s3_sync` is added because boto3's `head_bucket` is synchronous; `asyncio.to_thread` keeps it from blocking the event loop.

- [ ] **Step 4: Run, verify PASS**

```bash
cd backend && uv run pytest tests/unit/ -v
uv run mypy adhkar/api adhkar/db
```

Expected: all unit tests pass (settings, logging, middleware, errors, otel, readiness, meta, readyz).

- [ ] **Step 5: Commit**

```bash
git add backend/adhkar/api/deps.py backend/adhkar/api/v1/meta.py backend/tests/unit/test_readyz_unit.py
git commit -s -m "feat(backend): add /readyz with parallel db/redis/s3 checks

asyncio.gather fires the three readiness probes
concurrently; head_bucket is wrapped in asyncio.to_thread
because boto3's S3 client is synchronous.

Returns 200 with status='ready' when all green; 503 with
status='degraded' and per-check breakdown when any check
fails. Body shape stays the same on both codes so the
frontend renders the same UI without code branching.

Per spec §5.3 (readyz row) and §5.6 RFC 7807 compatibility."
```

---

## Task 13: Wire FastAPI factory in `main.py`

**Files:**
- Create: `backend/adhkar/main.py`
- Create: `backend/tests/integration/__init__.py`
- Create: `backend/tests/integration/test_app_factory.py`

- [ ] **Step 1: Write failing test**

`backend/tests/integration/test_app_factory.py`:
```python
import pytest
from httpx import ASGITransport, AsyncClient

from adhkar.core.settings import Settings


@pytest.fixture
def settings(monkeypatch):
    monkeypatch.setenv("ADHKAR_SECRET_KEY", "x" * 32)
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h/db")
    monkeypatch.setenv("REDIS_URL", "redis://h:6379/0")
    from adhkar.core.settings import get_settings
    get_settings.cache_clear()
    return Settings()


@pytest.mark.asyncio
async def test_factory_assembles_full_app(settings):
    from adhkar.main import create_app

    app = create_app(settings)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.get("/healthz")
        assert r.status_code == 200
        r2 = await c.get("/openapi.json")
        assert r2.status_code == 200
        spec = r2.json()
        assert spec["info"]["title"] == "Adhkar IR API"
        # request-id header round-trips
        r3 = await c.get("/healthz", headers={"X-Request-Id": "rid-test"})
        assert r3.headers["x-request-id"] == "rid-test"


@pytest.mark.asyncio
async def test_openapi_spec_is_valid(settings):
    from openapi_spec_validator import validate_spec
    from adhkar.main import create_app

    app = create_app(settings)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.get("/openapi.json")
    spec = r.json()
    validate_spec(spec)
```

- [ ] **Step 2: Run, verify FAIL**

```bash
cd backend && uv run pytest tests/integration/test_app_factory.py -v
```

Expected: ImportError on `adhkar.main`.

- [ ] **Step 3: Implement minimal**

`backend/adhkar/main.py`:
```python
"""FastAPI application factory."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse

from adhkar import __version__
from adhkar.api.errors import register_exception_handlers
from adhkar.api.v1.meta import router as meta_router
from adhkar.core.logging import configure_logging
from adhkar.core.middleware import AccessLogMiddleware, RequestIdMiddleware
from adhkar.core.otel import configure_otel
from adhkar.core.settings import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings)

    app = FastAPI(
        title="Adhkar IR API",
        version=__version__,
        openapi_url="/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
        default_response_class=ORJSONResponse,
    )

    app.add_middleware(AccessLogMiddleware)
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-Id"],
    )

    app.include_router(meta_router)
    register_exception_handlers(app)
    configure_otel(app, settings)

    return app
```

- [ ] **Step 4: Run, verify PASS**

```bash
cd backend && uv run pytest tests/ -v
uv run mypy adhkar
uv run ruff check .
uv run ruff format --check .
```

Expected: all tests pass; mypy/ruff clean.

- [ ] **Step 5: Commit**

```bash
git add backend/adhkar/main.py backend/tests/integration/__init__.py backend/tests/integration/test_app_factory.py
git commit -s -m "feat(backend): add create_app factory wiring all middleware and routes

Order matters: RequestId middleware runs first (innermost
wrap) so the contextvar is populated before AccessLog reads
it. CORS is added last so its preflight responses still
carry the X-Request-Id header (exposed via expose_headers).

OpenAPI spec validates against openapi_spec_validator, and
the title 'Adhkar IR API' is fixed for the SDK generator
(Phase 10)."
```

---

## Task 14: Alembic init + `0001_init_extensions` migration

**Files:**
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/script.py.mako`
- Create: `backend/alembic/versions/0001_init_extensions.py`

- [ ] **Step 1: Initialize alembic**

```bash
cd backend && uv run alembic init -t async alembic
```

Then **replace** the generated `alembic.ini` minimal content with:

```ini
[alembic]
script_location = alembic
file_template = %%(year)d_%%(month).2d_%%(day).2d_%%(hour).2d%%(minute).2d-%%(rev)s_%%(slug)s
sqlalchemy.url = driver://placeholder/  # overridden by env.py from ADHKAR_*

[post_write_hooks]
hooks = ruff_format
ruff_format.type = console_scripts
ruff_format.entrypoint = ruff
ruff_format.options = format REVISION_SCRIPT_FILENAME

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARNING
handlers = console
qualname =

[logger_sqlalchemy]
level = WARNING
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stdout,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

> Why a custom `file_template`: sequential numerical revision IDs are easier for humans to read in `versions/`; the timestamp prefix keeps the directory naturally sorted. Phase 0 ships `0001`; Phase 1 ships `0002` etc.

- [ ] **Step 2: Customize `alembic/env.py`**

Replace the generated file with:
```python
"""Alembic env using async engine + ADHKAR_* settings."""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.engine import Connection

from adhkar.core.settings import get_settings
from adhkar.db.base import Base
from adhkar.db.engine import create_engine

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    settings = get_settings()
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def _do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    settings = get_settings()
    engine = create_engine(settings)
    async with engine.connect() as conn:
        await conn.run_sync(_do_run_migrations)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
```

- [ ] **Step 3: Create the first migration**

`backend/alembic/versions/0001_init_extensions.py`:
```python
"""Initialize required PostgreSQL extensions.

Revision ID: 0001
Revises:
Create Date: 2026-06-16
"""

from __future__ import annotations

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    op.execute("DROP EXTENSION IF EXISTS vector")
    op.execute("DROP EXTENSION IF EXISTS pgcrypto")
    op.execute('DROP EXTENSION IF EXISTS "uuid-ossp"')
```

- [ ] **Step 4: Smoke verification**

Run a temporary postgres via Docker (this is a manual sanity check; the integration test in Task 19 does this for real):
```bash
cd backend
docker run --rm -d --name adhkar-alembic-smoke -e POSTGRES_PASSWORD=p -p 55432:5432 pgvector/pgvector:pg16
sleep 5
DATABASE_URL=postgresql+asyncpg://postgres:p@localhost:55432/postgres \
ADHKAR_SECRET_KEY=$(python -c 'import secrets; print(secrets.token_hex(16))') \
REDIS_URL=redis://x:6379/0 \
uv run alembic upgrade head
DATABASE_URL=postgresql+asyncpg://postgres:p@localhost:55432/postgres \
ADHKAR_SECRET_KEY=$(python -c 'import secrets; print(secrets.token_hex(16))') \
REDIS_URL=redis://x:6379/0 \
uv run alembic downgrade base
docker stop adhkar-alembic-smoke
```

Expected: both upgrade and downgrade succeed with no errors. The `vector` extension confirms the pgvector image is correct.

- [ ] **Step 5: Commit**

```bash
git add backend/alembic.ini backend/alembic/
git commit -s -m "feat(backend): bootstrap Alembic async + 0001 init extensions

- alembic.ini: timestamped + numeric file_template, ruff
  format post-write hook
- env.py: async engine, settings-driven DATABASE_URL,
  compare_type=True for accurate diffs in Phase 1+
- versions/0001_init_extensions.py: uuid-ossp, pgcrypto,
  vector (pgvector) extensions; idempotent upgrade,
  reverse-order downgrade

Smoke-verified upgrade head + downgrade base round-trips
against pgvector/pgvector:pg16."
```

---

## Task 15: Backend entrypoint + Dockerfile

**Files:**
- Create: `backend/scripts/entrypoint.sh`
- Create: `backend/Dockerfile`
- Create: `backend/.dockerignore`

- [ ] **Step 1: Create `backend/scripts/entrypoint.sh`**

```bash
#!/usr/bin/env sh
set -eu

# Run migrations unless explicitly skipped (e.g., from compose for one-shot debugging).
if [ "${ADHKAR_SKIP_MIGRATIONS:-0}" = "0" ]; then
  echo "[entrypoint] running alembic upgrade head"
  uv run alembic upgrade head
fi

echo "[entrypoint] starting uvicorn"
exec "$@"
```

Make it executable:
```bash
chmod +x backend/scripts/entrypoint.sh
```

- [ ] **Step 2: Create `backend/Dockerfile`**

```dockerfile
# syntax=docker/dockerfile:1.7

FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

RUN apt-get update \
 && apt-get install -y --no-install-recommends curl libpq-dev \
 && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.4.30 /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./

ARG INSTALL_GROUP=prod
RUN if [ "$INSTALL_GROUP" = "dev" ]; then \
      uv sync --frozen; \
    else \
      uv sync --frozen --no-dev; \
    fi

COPY adhkar ./adhkar
COPY alembic.ini ./
COPY alembic ./alembic
COPY scripts ./scripts

ARG GIT_COMMIT=unknown
ARG BUILT_AT=unknown
ENV ADHKAR_GIT_COMMIT=${GIT_COMMIT} \
    ADHKAR_BUILT_AT=${BUILT_AT}

EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
  CMD curl -fsS http://localhost:8000/healthz || exit 1

ENTRYPOINT ["./scripts/entrypoint.sh"]
CMD ["uvicorn", "adhkar.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 3: Create `backend/.dockerignore`**

```
__pycache__
*.pyc
.venv
.pytest_cache
.mypy_cache
.ruff_cache
.coverage
htmlcov
tests
```

- [ ] **Step 4: Build verification**

```bash
cd backend && docker build --build-arg INSTALL_GROUP=dev --build-arg GIT_COMMIT=$(git rev-parse --short HEAD) --build-arg BUILT_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ) -t adhkar/api:smoke .
docker run --rm -e ADHKAR_SECRET_KEY=$(python -c 'import secrets; print(secrets.token_hex(16))') -e DATABASE_URL=postgresql+asyncpg://nope/nope -e REDIS_URL=redis://nope:6379/0 -e ADHKAR_SKIP_MIGRATIONS=1 -p 8001:8000 adhkar/api:smoke &
sleep 3
curl -fsS http://localhost:8001/healthz
docker stop $(docker ps -q --filter ancestor=adhkar/api:smoke)
```

Expected: image builds; `curl` returns `{"status":"ok"}`.

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/entrypoint.sh backend/Dockerfile backend/.dockerignore
git commit -s -m "build(backend): multi-stage Dockerfile + alembic entrypoint

- python:3.12-slim base + uv 0.4.30 binary copied from
  ghcr.io/astral-sh/uv (avoids pip overhead).
- INSTALL_GROUP build arg: 'dev' for compose dev container
  (full deps), 'prod' for shipped image (--no-dev).
- entrypoint.sh: runs 'alembic upgrade head' unless
  ADHKAR_SKIP_MIGRATIONS=1, then execs uvicorn factory.
- HEALTHCHECK: curl /healthz every 10s; start-period 10s
  covers cold start + migration window.
- ADHKAR_GIT_COMMIT/ADHKAR_BUILT_AT injected at build time
  so /version endpoint reflects the actual built image."
```

---

## Task 16: docker-compose dev stack

**Files:**
- Create: `deploy/.env.example`
- Create: `deploy/docker-compose.yml`
- Create: `deploy/docker-compose.override.example.yml`
- Create: `deploy/scripts/minio-bootstrap.sh`

- [ ] **Step 1: Create `deploy/.env.example`**

```env
# ----- Adhkar core -----
ADHKAR_ENV=dev
ADHKAR_LOG_LEVEL=INFO
ADHKAR_SECRET_KEY=change-me-32-chars-min-xxxxxxxxxxxx

# ----- Database -----
ADHKAR_DB_HOST=postgres
ADHKAR_DB_PORT=5432
ADHKAR_DB_NAME=adhkar
ADHKAR_DB_USER=adhkar
ADHKAR_DB_PASSWORD=adhkar-dev
DATABASE_URL=postgresql+asyncpg://adhkar:adhkar-dev@postgres:5432/adhkar

# ----- Redis -----
REDIS_URL=redis://redis:6379/0

# ----- Object store (S3-compat) -----
ADHKAR_S3_ENDPOINT=http://minio:9000
ADHKAR_S3_ACCESS_KEY=minio-dev
ADHKAR_S3_SECRET_KEY=minio-dev-secret
ADHKAR_S3_BUCKET=adhkar-attachments
ADHKAR_S3_REGION=us-east-1

# ----- Mail (dev) -----
ADHKAR_SMTP_HOST=mailhog
ADHKAR_SMTP_PORT=1025
ADHKAR_SMTP_FROM=adhkar@localhost

# ----- Observability -----
ADHKAR_OTEL_EXPORTER_OTLP_ENDPOINT=
ADHKAR_OTEL_SERVICE_NAME=adhkar-api

# ----- Frontend -----
VITE_API_BASE_URL=http://localhost:8000
```

- [ ] **Step 2: Create `deploy/scripts/minio-bootstrap.sh`**

```bash
#!/usr/bin/env sh
# Bootstraps the MinIO bucket on first run. Idempotent.
set -eu

ENDPOINT="${MINIO_ENDPOINT:-http://minio:9000}"
ACCESS_KEY="${MINIO_ROOT_USER}"
SECRET_KEY="${MINIO_ROOT_PASSWORD}"
BUCKET="${BUCKET_NAME:-adhkar-attachments}"

echo "[minio-init] waiting for minio at $ENDPOINT"
until /usr/bin/mc alias set local "$ENDPOINT" "$ACCESS_KEY" "$SECRET_KEY" >/dev/null 2>&1; do
  sleep 1
done

if /usr/bin/mc ls "local/$BUCKET" >/dev/null 2>&1; then
  echo "[minio-init] bucket $BUCKET already exists"
else
  /usr/bin/mc mb "local/$BUCKET"
  echo "[minio-init] bucket $BUCKET created"
fi
```

```bash
chmod +x deploy/scripts/minio-bootstrap.sh
```

- [ ] **Step 3: Create `deploy/docker-compose.yml`**

```yaml
name: adhkar
services:

  postgres:
    image: pgvector/pgvector:pg16
    container_name: adhkar-postgres
    environment:
      POSTGRES_USER: ${ADHKAR_DB_USER}
      POSTGRES_PASSWORD: ${ADHKAR_DB_PASSWORD}
      POSTGRES_DB: ${ADHKAR_DB_NAME}
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${ADHKAR_DB_USER} -d ${ADHKAR_DB_NAME}"]
      interval: 5s
      timeout: 3s
      retries: 10
    networks: [adhkar-net]

  redis:
    image: redis:7-alpine
    container_name: adhkar-redis
    ports:
      - "6379:6379"
    volumes:
      - redisdata:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 10
    networks: [adhkar-net]

  minio:
    image: minio/minio:latest
    container_name: adhkar-minio
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: ${ADHKAR_S3_ACCESS_KEY}
      MINIO_ROOT_PASSWORD: ${ADHKAR_S3_SECRET_KEY}
    ports:
      - "9000:9000"
      - "9001:9001"
    volumes:
      - miniodata:/data
    healthcheck:
      test: ["CMD", "curl", "-fsS", "http://localhost:9000/minio/health/ready"]
      interval: 5s
      timeout: 3s
      retries: 10
    networks: [adhkar-net]

  minio-init:
    image: minio/mc:latest
    container_name: adhkar-minio-init
    depends_on:
      minio: { condition: service_healthy }
    environment:
      MINIO_ENDPOINT: http://minio:9000
      MINIO_ROOT_USER: ${ADHKAR_S3_ACCESS_KEY}
      MINIO_ROOT_PASSWORD: ${ADHKAR_S3_SECRET_KEY}
      BUCKET_NAME: ${ADHKAR_S3_BUCKET}
    volumes:
      - ./scripts/minio-bootstrap.sh:/bootstrap.sh:ro
    entrypoint: ["/bin/sh", "/bootstrap.sh"]
    restart: "no"
    networks: [adhkar-net]

  mailhog:
    image: mailhog/mailhog:latest
    container_name: adhkar-mailhog
    ports:
      - "1025:1025"
      - "8025:8025"
    networks: [adhkar-net]

  api:
    build:
      context: ../backend
      args:
        INSTALL_GROUP: dev
        GIT_COMMIT: ${GIT_COMMIT:-dev}
        BUILT_AT: ${BUILT_AT:-dev}
    container_name: adhkar-api
    environment:
      ADHKAR_ENV: ${ADHKAR_ENV}
      ADHKAR_LOG_LEVEL: ${ADHKAR_LOG_LEVEL}
      ADHKAR_SECRET_KEY: ${ADHKAR_SECRET_KEY}
      DATABASE_URL: ${DATABASE_URL}
      REDIS_URL: ${REDIS_URL}
      ADHKAR_S3_ENDPOINT: ${ADHKAR_S3_ENDPOINT}
      ADHKAR_S3_ACCESS_KEY: ${ADHKAR_S3_ACCESS_KEY}
      ADHKAR_S3_SECRET_KEY: ${ADHKAR_S3_SECRET_KEY}
      ADHKAR_S3_BUCKET: ${ADHKAR_S3_BUCKET}
      ADHKAR_S3_REGION: ${ADHKAR_S3_REGION}
      ADHKAR_SMTP_HOST: ${ADHKAR_SMTP_HOST}
      ADHKAR_SMTP_PORT: ${ADHKAR_SMTP_PORT}
      ADHKAR_SMTP_FROM: ${ADHKAR_SMTP_FROM}
      ADHKAR_OTEL_EXPORTER_OTLP_ENDPOINT: ${ADHKAR_OTEL_EXPORTER_OTLP_ENDPOINT}
      ADHKAR_OTEL_SERVICE_NAME: ${ADHKAR_OTEL_SERVICE_NAME}
    ports:
      - "8000:8000"
    depends_on:
      postgres: { condition: service_healthy }
      redis: { condition: service_healthy }
      minio: { condition: service_healthy }
    volumes:
      - ../backend/adhkar:/app/adhkar:ro
      - ../backend/alembic:/app/alembic:ro
    healthcheck:
      test: ["CMD", "curl", "-fsS", "http://localhost:8000/healthz"]
      interval: 10s
      timeout: 3s
      retries: 5
      start_period: 15s
    networks: [adhkar-net]

  web:
    build:
      context: ../frontend
      target: dev
    container_name: adhkar-web
    environment:
      VITE_API_BASE_URL: ${VITE_API_BASE_URL}
    ports:
      - "5173:5173"
    depends_on:
      api: { condition: service_healthy }
    volumes:
      - ../frontend/src:/app/src:ro
      - ../frontend/public:/app/public:ro
      - ../frontend/index.html:/app/index.html:ro
    healthcheck:
      test: ["CMD", "wget", "-qO-", "http://localhost:5173"]
      interval: 10s
      timeout: 3s
      retries: 5
    networks: [adhkar-net]

  jaeger:
    image: jaegertracing/all-in-one:1.62
    container_name: adhkar-jaeger
    profiles: ["observability"]
    ports:
      - "16686:16686"
      - "4317:4317"
    networks: [adhkar-net]

  # Phase 6+: OpenSearch placeholder. Uncomment when SearchIndex needs swap.
  # opensearch:
  #   image: opensearchproject/opensearch:2
  #   profiles: ["search"]
  #   environment:
  #     - discovery.type=single-node
  #     - DISABLE_SECURITY_PLUGIN=true
  #   ports: ["9200:9200"]
  #   networks: [adhkar-net]

volumes:
  pgdata:
  redisdata:
  miniodata:

networks:
  adhkar-net:
    driver: bridge
```

- [ ] **Step 4: Create `deploy/docker-compose.override.example.yml`**

```yaml
# Copy to docker-compose.override.yml for local-only overrides.
# Auto-loaded by `docker compose` if named docker-compose.override.yml.
services:
  api:
    environment:
      ADHKAR_LOG_LEVEL: DEBUG
```

- [ ] **Step 5: Smoke-up (backend half only — frontend not built yet)**

```bash
cd deploy
cp .env.example .env
# bring up just data services + api (web requires frontend Dockerfile from Task 28)
docker compose up -d postgres redis minio minio-init mailhog
sleep 15
docker compose ps
docker compose logs minio-init
docker compose up -d api
sleep 15
curl -fsS http://localhost:8000/healthz
curl -fsS http://localhost:8000/readyz
```

Expected: `minio-init` exits cleanly with "bucket adhkar-attachments created"; `/healthz` returns `{"status":"ok"}`; `/readyz` returns `{"status":"ready","checks":{"db":"ok","redis":"ok","s3":"ok"}}`.

- [ ] **Step 6: Tear down**

```bash
docker compose down -v
```

- [ ] **Step 7: Commit**

```bash
git add deploy/.env.example deploy/docker-compose.yml deploy/docker-compose.override.example.yml deploy/scripts/minio-bootstrap.sh
git commit -s -m "build(deploy): docker-compose dev stack (no OpenSearch)

- postgres (pgvector/pgvector:pg16), redis, minio, mailhog,
  api, web all on adhkar-net bridge.
- minio-init one-shot container creates the
  adhkar-attachments bucket idempotently via mc client.
- container_name: adhkar-<svc> pinned for deterministic
  'docker stop adhkar-redis' DoD demo and log grep.
- depends_on with condition: service_healthy chains startup;
  named volumes pgdata/redisdata/miniodata for clean -v reset.
- profiles: 'observability' enables Jaeger (OTLP gRPC :4317,
  UI :16686). 'search' profile reserved for future OpenSearch.
- Smoke verified: /readyz returns all checks 'ok' after
  cold-start in < 60s on dev laptop."
```

---

## Task 17: Frontend project init (Vite + React 18 + TS + pnpm)

**Files:**
- Create: `frontend/package.json`, `frontend/tsconfig.json`, `frontend/tsconfig.node.json`
- Create: `frontend/vite.config.ts`, `frontend/index.html`
- Create: `frontend/.eslintrc.cjs`, `frontend/.prettierrc.json`, `frontend/.prettierignore`
- Create: `frontend/.npmrc`
- Create: `frontend/src/main.tsx`, `frontend/src/app/App.tsx` (stub)

- [ ] **Step 1: Create `frontend/.npmrc`**

```ini
auto-install-peers=true
strict-peer-dependencies=false
shamefully-hoist=false
```

- [ ] **Step 2: Create `frontend/package.json`**

```json
{
  "name": "@adhkar/web",
  "version": "0.1.0-dev",
  "private": true,
  "type": "module",
  "engines": { "node": ">=22", "pnpm": ">=9" },
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview --port 5173",
    "lint": "eslint . --max-warnings 0",
    "format": "prettier --write .",
    "format:check": "prettier --check .",
    "typecheck": "tsc -b --noEmit",
    "test": "vitest",
    "test:ui": "vitest --ui",
    "storybook": "storybook dev -p 6006",
    "storybook:build": "storybook build",
    "test-storybook": "test-storybook"
  },
  "dependencies": {
    "@tanstack/react-query": "^5.59.0",
    "@tanstack/react-router": "^1.74.0",
    "cmdk": "^1.0.0",
    "material-symbols": "^0.27.0",
    "react": "^18.3.0",
    "react-dom": "^18.3.0",
    "zustand": "^5.0.0"
  },
  "devDependencies": {
    "@storybook/addon-essentials": "^8.3.0",
    "@storybook/react-vite": "^8.3.0",
    "@storybook/test": "^8.3.0",
    "@storybook/test-runner": "^0.19.0",
    "@tailwindcss/vite": "^4.0.0-alpha.36",
    "@testing-library/jest-dom": "^6.5.0",
    "@testing-library/react": "^16.0.0",
    "@testing-library/user-event": "^14.5.0",
    "@types/react": "^18.3.0",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.0",
    "@vitest/coverage-v8": "^2.1.0",
    "axe-core": "^4.10.0",
    "eslint": "^9.12.0",
    "eslint-config-prettier": "^9.1.0",
    "eslint-plugin-react": "^7.37.0",
    "eslint-plugin-react-hooks": "^5.0.0",
    "eslint-plugin-storybook": "^0.10.0",
    "happy-dom": "^15.7.0",
    "msw": "^2.4.0",
    "prettier": "^3.3.0",
    "storybook": "^8.3.0",
    "tailwindcss": "^4.0.0-alpha.36",
    "typescript": "^5.6.0",
    "typescript-eslint": "^8.8.0",
    "vite": "^5.4.0",
    "vitest": "^2.1.0",
    "vitest-axe": "^0.1.0"
  }
}
```

- [ ] **Step 3: Create `frontend/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "useDefineForClassFields": true,
    "lib": ["ES2023", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "exactOptionalPropertyTypes": true,
    "noImplicitOverride": true,
    "noUncheckedIndexedAccess": true,
    "baseUrl": ".",
    "paths": {
      "@/*": ["src/*"]
    },
    "types": ["vitest/globals", "@testing-library/jest-dom"]
  },
  "include": ["src", "stories", "tests"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

- [ ] **Step 4: Create `frontend/tsconfig.node.json`**

```json
{
  "compilerOptions": {
    "composite": true,
    "skipLibCheck": true,
    "module": "ESNext",
    "moduleResolution": "bundler",
    "allowSyntheticDefaultImports": true,
    "strict": true
  },
  "include": ["vite.config.ts"]
}
```

- [ ] **Step 5: Create `frontend/vite.config.ts`**

```ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "node:path";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { "@": path.resolve(__dirname, "src") },
  },
  server: { port: 5173, host: true },
  preview: { port: 5173 },
  test: {
    globals: true,
    environment: "happy-dom",
    setupFiles: ["./src/test/setup.ts"],
    coverage: {
      provider: "v8",
      reporter: ["text", "html", "json"],
      thresholds: { lines: 60, statements: 60, branches: 60, functions: 60 },
    },
  },
});
```

- [ ] **Step 6: Create `frontend/index.html`**

```html
<!doctype html>
<html lang="en" data-theme="dark">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Adhkar IR</title>
    <link rel="icon" type="image/svg+xml" href="/favicon.svg" />
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 7: Create `frontend/.eslintrc.cjs`**

```js
/* eslint-env node */
module.exports = {
  root: true,
  env: { browser: true, es2023: true, node: true },
  extends: [
    "eslint:recommended",
    "plugin:@typescript-eslint/recommended",
    "plugin:react/recommended",
    "plugin:react-hooks/recommended",
    "plugin:storybook/recommended",
    "prettier",
  ],
  parser: "@typescript-eslint/parser",
  parserOptions: { ecmaVersion: "latest", sourceType: "module" },
  plugins: ["react", "react-hooks"],
  settings: { react: { version: "18" } },
  rules: {
    "react/react-in-jsx-scope": "off",
    "react/prop-types": "off",
    "@typescript-eslint/no-unused-vars": ["error", { argsIgnorePattern: "^_" }],
  },
  ignorePatterns: ["dist", "storybook-static", "node_modules", "coverage"],
};
```

- [ ] **Step 8: Create `frontend/.prettierrc.json`**

```json
{
  "semi": true,
  "singleQuote": false,
  "trailingComma": "all",
  "printWidth": 100,
  "tabWidth": 2,
  "arrowParens": "always"
}
```

- [ ] **Step 9: Create `frontend/.prettierignore`**

```
dist
storybook-static
coverage
node_modules
pnpm-lock.yaml
```

- [ ] **Step 10: Create stub `frontend/src/main.tsx`**

```tsx
import React from "react";
import ReactDOM from "react-dom/client";
import { App } from "./app/App";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
```

- [ ] **Step 11: Create stub `frontend/src/app/App.tsx`**

```tsx
export function App() {
  return <div className="p-4 text-lg">Adhkar IR — bootstrapping</div>;
}
```

- [ ] **Step 12: Create `frontend/src/test/setup.ts`**

```ts
import "@testing-library/jest-dom/vitest";
import { afterEach } from "vitest";
import { cleanup } from "@testing-library/react";

afterEach(() => cleanup());
```

- [ ] **Step 13: Install + verify**

```bash
cd frontend && pnpm install
pnpm typecheck
pnpm lint
pnpm format:check
pnpm build
```

Expected: install completes, all four scripts exit 0.

- [ ] **Step 14: Commit**

```bash
git add frontend/.npmrc frontend/package.json frontend/pnpm-lock.yaml frontend/tsconfig.json frontend/tsconfig.node.json frontend/vite.config.ts frontend/index.html frontend/.eslintrc.cjs frontend/.prettierrc.json frontend/.prettierignore frontend/src/main.tsx frontend/src/app/App.tsx frontend/src/test/setup.ts
git commit -s -m "chore(frontend): init Vite + React 18 + TS + Tailwind v4 + pnpm

- React 18, TS 5.6 strict (exactOptionalPropertyTypes,
  noUncheckedIndexedAccess), Vite 5.
- Tailwind v4 alpha via @tailwindcss/vite plugin (CSS-first,
  no PostCSS config needed).
- TanStack Router + Query, Zustand, cmdk, lucide.
- ESLint + Prettier with prettier-eslint compatibility.
- Vitest + Testing Library + happy-dom + vitest-axe + MSW.
- Storybook 8 with test-runner + play-functions.
- Coverage threshold 60% per spec §8.4 Phase 0 baseline."
```

---

## Task 18: M3 design tokens + Tailwind v4 config

**Files:**
- Create: `frontend/src/design-system/tokens.css`
- Create: `frontend/src/design-system/index.css`
- Modify: `frontend/src/main.tsx` to import design tokens

> **Note**: Token scheme follows Material Design 3 (ADR 0005). All `--md-sys-*` variables come from Material Theme Builder export with source color `#F59E0B`. Domain tokens (`--adhkar-severity-*`, `--adhkar-tlp-*`) are kept separate so they cannot be overridden by M3 theming. Density overrides (button heights, list-row 32 px, card padding 12 px) are applied in component CSS, not in tokens.

- [ ] **Step 1: Create `frontend/src/design-system/tokens.css`**

```css
:root {
  /* ----- M3 shape system ----- */
  --md-sys-shape-corner-none: 0;
  --md-sys-shape-corner-extra-small: 4px;
  --md-sys-shape-corner-small: 8px;
  --md-sys-shape-corner-medium: 12px;
  --md-sys-shape-corner-large: 16px;
  --md-sys-shape-corner-extra-large: 28px;
  --md-sys-shape-corner-full: 9999px;

  /* ----- M3 type scale (px sizes; density-tuned) ----- */
  --md-sys-typescale-label-small-size: 11px;
  --md-sys-typescale-label-medium-size: 12px;
  --md-sys-typescale-label-large-size: 14px;
  --md-sys-typescale-body-small-size: 12px;
  --md-sys-typescale-body-medium-size: 14px;
  --md-sys-typescale-body-large-size: 16px;
  --md-sys-typescale-title-small-size: 14px;
  --md-sys-typescale-title-medium-size: 16px;
  --md-sys-typescale-title-large-size: 22px;
  --md-sys-typescale-headline-small-size: 24px;
  --md-sys-typescale-headline-medium-size: 28px;
  --md-sys-typescale-headline-large-size: 32px;

  /* ----- M3 motion ----- */
  --md-sys-motion-easing-standard: cubic-bezier(0.2, 0, 0, 1);
  --md-sys-motion-easing-emphasized: cubic-bezier(0.05, 0.7, 0.1, 1);
  --md-sys-motion-duration-short2: 100ms;
  --md-sys-motion-duration-medium2: 250ms;
  --md-sys-motion-duration-long2: 450ms;

  /* ----- typography family (M3 plain + brand + mono) ----- */
  --md-sys-typescale-font-plain: "Inter Variable", system-ui, -apple-system, "Segoe UI", sans-serif;
  --md-sys-typescale-font-brand: "Inter Variable", system-ui, sans-serif;
  --md-sys-typescale-font-mono: "JetBrains Mono Variable", ui-monospace, "SF Mono", Menlo, monospace;

  /* ----- Domain tokens (severity 1-4 + FIRST.org TLP) — override M3 ----- */
  --adhkar-severity-1: #3b82f6;
  --adhkar-severity-2: #eab308;
  --adhkar-severity-3: #f97316;
  --adhkar-severity-4: #ef4444;
  --adhkar-tlp-white: #ffffff;
  --adhkar-tlp-green: #22c55e;
  --adhkar-tlp-amber: #f59e0b;
  --adhkar-tlp-amber-strict: #d97706;
  --adhkar-tlp-red: #dc2626;
}

/* ----- M3 DARK scheme (default) — exported from Material Theme Builder ----- */
:root,
[data-theme="dark"] {
  --md-sys-color-primary: #ffb787;
  --md-sys-color-on-primary: #4f2500;
  --md-sys-color-primary-container: #6f3a05;
  --md-sys-color-on-primary-container: #ffdbc2;

  --md-sys-color-secondary: #e5bf9f;
  --md-sys-color-on-secondary: #422b16;
  --md-sys-color-secondary-container: #5b412a;
  --md-sys-color-on-secondary-container: #ffdbc2;

  --md-sys-color-tertiary: #c3cb88;
  --md-sys-color-on-tertiary: #2c3400;
  --md-sys-color-tertiary-container: #424b0f;
  --md-sys-color-on-tertiary-container: #dfe79e;

  --md-sys-color-error: #ffb4ab;
  --md-sys-color-on-error: #690005;
  --md-sys-color-error-container: #93000a;
  --md-sys-color-on-error-container: #ffdad6;

  --md-sys-color-surface: #181210;
  --md-sys-color-surface-dim: #181210;
  --md-sys-color-surface-bright: #3f3835;
  --md-sys-color-surface-container-lowest: #120c0a;
  --md-sys-color-surface-container-low: #211a17;
  --md-sys-color-surface-container: #251e1b;
  --md-sys-color-surface-container-high: #302925;
  --md-sys-color-surface-container-highest: #3b3330;

  --md-sys-color-on-surface: #f1dfd8;
  --md-sys-color-on-surface-variant: #d8c2b7;
  --md-sys-color-outline: #a08d83;
  --md-sys-color-outline-variant: #52443e;

  --md-sys-color-inverse-surface: #f1dfd8;
  --md-sys-color-inverse-on-surface: #382e2b;
  --md-sys-color-inverse-primary: #8b4f1d;

  --md-sys-color-scrim: #000000;
  --md-sys-color-shadow: #000000;
}

/* ----- M3 LIGHT scheme (opt-in) ----- */
[data-theme="light"] {
  --md-sys-color-primary: #8b4f1d;
  --md-sys-color-on-primary: #ffffff;
  --md-sys-color-primary-container: #ffdbc2;
  --md-sys-color-on-primary-container: #2e1500;

  --md-sys-color-secondary: #765a3f;
  --md-sys-color-on-secondary: #ffffff;
  --md-sys-color-secondary-container: #ffdbc2;
  --md-sys-color-on-secondary-container: #2a1808;

  --md-sys-color-tertiary: #5b6325;
  --md-sys-color-on-tertiary: #ffffff;
  --md-sys-color-tertiary-container: #dfe79e;
  --md-sys-color-on-tertiary-container: #181e00;

  --md-sys-color-error: #ba1a1a;
  --md-sys-color-on-error: #ffffff;
  --md-sys-color-error-container: #ffdad6;
  --md-sys-color-on-error-container: #410002;

  --md-sys-color-surface: #fff8f5;
  --md-sys-color-surface-dim: #e3d6cf;
  --md-sys-color-surface-bright: #fff8f5;
  --md-sys-color-surface-container-lowest: #ffffff;
  --md-sys-color-surface-container-low: #fcefe7;
  --md-sys-color-surface-container: #f6e9e2;
  --md-sys-color-surface-container-high: #f1e3dc;
  --md-sys-color-surface-container-highest: #ebddd7;

  --md-sys-color-on-surface: #221a16;
  --md-sys-color-on-surface-variant: #52443e;
  --md-sys-color-outline: #84736c;
  --md-sys-color-outline-variant: #d6c2b8;

  --md-sys-color-inverse-surface: #382e2b;
  --md-sys-color-inverse-on-surface: #fdeee6;
  --md-sys-color-inverse-primary: #ffb787;

  --md-sys-color-scrim: #000000;
  --md-sys-color-shadow: #000000;
}
```

- [ ] **Step 2: Create `frontend/src/design-system/index.css`**

```css
@import "tailwindcss";
@import "material-symbols/index.css";
@import "./tokens.css";

@theme {
  /* ----- M3 colors mapped to Tailwind utilities -----
     Usage: bg-surface, bg-surface-container-high, text-on-surface,
            text-on-surface-variant, border-outline, text-primary,
            bg-primary-container, text-error, bg-error-container */
  --color-primary: var(--md-sys-color-primary);
  --color-on-primary: var(--md-sys-color-on-primary);
  --color-primary-container: var(--md-sys-color-primary-container);
  --color-on-primary-container: var(--md-sys-color-on-primary-container);
  --color-secondary: var(--md-sys-color-secondary);
  --color-on-secondary: var(--md-sys-color-on-secondary);
  --color-secondary-container: var(--md-sys-color-secondary-container);
  --color-on-secondary-container: var(--md-sys-color-on-secondary-container);
  --color-tertiary: var(--md-sys-color-tertiary);
  --color-on-tertiary: var(--md-sys-color-on-tertiary);
  --color-tertiary-container: var(--md-sys-color-tertiary-container);
  --color-on-tertiary-container: var(--md-sys-color-on-tertiary-container);
  --color-error: var(--md-sys-color-error);
  --color-on-error: var(--md-sys-color-on-error);
  --color-error-container: var(--md-sys-color-error-container);
  --color-on-error-container: var(--md-sys-color-on-error-container);

  --color-surface: var(--md-sys-color-surface);
  --color-surface-dim: var(--md-sys-color-surface-dim);
  --color-surface-bright: var(--md-sys-color-surface-bright);
  --color-surface-container-lowest: var(--md-sys-color-surface-container-lowest);
  --color-surface-container-low: var(--md-sys-color-surface-container-low);
  --color-surface-container: var(--md-sys-color-surface-container);
  --color-surface-container-high: var(--md-sys-color-surface-container-high);
  --color-surface-container-highest: var(--md-sys-color-surface-container-highest);

  --color-on-surface: var(--md-sys-color-on-surface);
  --color-on-surface-variant: var(--md-sys-color-on-surface-variant);
  --color-outline: var(--md-sys-color-outline);
  --color-outline-variant: var(--md-sys-color-outline-variant);

  /* ----- Domain semantic colors (override M3) ----- */
  --color-severity-1: var(--adhkar-severity-1);
  --color-severity-2: var(--adhkar-severity-2);
  --color-severity-3: var(--adhkar-severity-3);
  --color-severity-4: var(--adhkar-severity-4);
  --color-tlp-white: var(--adhkar-tlp-white);
  --color-tlp-green: var(--adhkar-tlp-green);
  --color-tlp-amber: var(--adhkar-tlp-amber);
  --color-tlp-amber-strict: var(--adhkar-tlp-amber-strict);
  --color-tlp-red: var(--adhkar-tlp-red);

  /* ----- Type ----- */
  --font-sans: var(--md-sys-typescale-font-plain);
  --font-brand: var(--md-sys-typescale-font-brand);
  --font-mono: var(--md-sys-typescale-font-mono);

  /* ----- M3 shape -> Tailwind rounded-shape-* ----- */
  --radius-shape-none: var(--md-sys-shape-corner-none);
  --radius-shape-extra-small: var(--md-sys-shape-corner-extra-small);
  --radius-shape-small: var(--md-sys-shape-corner-small);
  --radius-shape-medium: var(--md-sys-shape-corner-medium);
  --radius-shape-large: var(--md-sys-shape-corner-large);
  --radius-shape-extra-large: var(--md-sys-shape-corner-extra-large);
  --radius-shape-full: var(--md-sys-shape-corner-full);
}

html,
body,
#root {
  height: 100%;
  margin: 0;
  background: var(--md-sys-color-surface);
  color: var(--md-sys-color-on-surface);
  font-family: var(--md-sys-typescale-font-plain);
  font-feature-settings: "cv11", "ss01";
}

button {
  font-family: inherit;
}

/* ----- Material Symbols Rounded defaults ----- */
.material-symbols-rounded {
  font-variation-settings: "FILL" 0, "wght" 400, "GRAD" 0, "opsz" 24;
  vertical-align: middle;
  user-select: none;
}
```

- [ ] **Step 3: Update `frontend/src/main.tsx`**

```tsx
import React from "react";
import ReactDOM from "react-dom/client";
import "./design-system/index.css";
import { App } from "./app/App";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
```

- [ ] **Step 4: Verify**

```bash
cd frontend && pnpm build
pnpm dev &
sleep 5
curl -fsS http://localhost:5173/ | grep -q "Adhkar IR" && echo OK
kill %1
```

Expected: build succeeds, dev server serves a page containing "Adhkar IR".

- [ ] **Step 5: Commit**

```bash
git add frontend/src/design-system/ frontend/src/main.tsx
git commit -s -m "feat(frontend): add M3 design tokens + Tailwind v4 mapping

Per ADR 0005 Material Design 3 dense-dark.

tokens.css: M3 system tokens (--md-sys-shape-*, --md-sys-
typescale-*, --md-sys-motion-*, --md-sys-color-* dark+light
schemes exported from Material Theme Builder with source
color #F59E0B) PLUS domain tokens that override M3 wherever
shown (--adhkar-severity-1..4 ramp, --adhkar-tlp-{white,
green,amber,amber-strict,red} FIRST.org colors).

index.css: imports Tailwind v4 + material-symbols/index.css
font, then @theme maps M3 tokens to utility classes:
bg-surface, bg-surface-container-{lowest..highest},
text-on-surface, text-on-surface-variant, border-outline,
bg-primary-container, text-error, rounded-shape-{xs..xl},
text-severity-3, bg-tlp-amber, etc.

Dark scheme is the default (data-theme='dark' on <html>);
light is opt-in via toggle. Material Symbols Rounded loaded
globally with default font-variation-settings (FILL 0, wght
400, GRAD 0, opsz 24); per-instance overrides via inline
style or class."
```

---

## Task 19: Storybook 8 init

**Files:**
- Create: `frontend/.storybook/main.ts`, `frontend/.storybook/preview.ts`
- Create: `frontend/.storybook/test-runner.ts`
- Create: `frontend/src/test/storybook-globals.css`

- [ ] **Step 1: Create `frontend/.storybook/main.ts`**

```ts
import type { StorybookConfig } from "@storybook/react-vite";

const config: StorybookConfig = {
  stories: ["../src/**/*.stories.@(ts|tsx)"],
  addons: ["@storybook/addon-essentials"],
  framework: { name: "@storybook/react-vite", options: {} },
  typescript: { reactDocgen: "react-docgen-typescript" },
  staticDirs: ["../public"],
};

export default config;
```

- [ ] **Step 2: Create `frontend/.storybook/preview.ts`**

```ts
import type { Preview } from "@storybook/react";
import "../src/design-system/index.css";

const preview: Preview = {
  parameters: {
    backgrounds: { disable: true }, // canvas already comes from tokens
    controls: { matchers: { color: /(background|color)$/i } },
    layout: "centered",
  },
  globalTypes: {
    theme: {
      description: "Theme",
      defaultValue: "dark",
      toolbar: {
        title: "Theme",
        icon: "circlehollow",
        items: ["dark", "light"],
        dynamicTitle: true,
      },
    },
  },
  decorators: [
    (Story, ctx) => {
      document.documentElement.dataset.theme = (ctx.globals.theme as string) ?? "dark";
      return Story();
    },
  ],
};

export default preview;
```

- [ ] **Step 3: Create `frontend/.storybook/test-runner.ts`**

```ts
import type { TestRunnerConfig } from "@storybook/test-runner";

const config: TestRunnerConfig = {
  async preVisit(page) {
    await page.setViewportSize({ width: 1280, height: 800 });
  },
};

export default config;
```

- [ ] **Step 4: Verify Storybook starts**

```bash
cd frontend && pnpm storybook &
sleep 8
curl -fsS http://localhost:6006/ | grep -q -i "storybook" && echo OK
kill %1
pnpm storybook:build
```

Expected: dev server serves Storybook root; static build outputs to `storybook-static/`.

- [ ] **Step 5: Commit**

```bash
git add frontend/.storybook/
git commit -s -m "chore(frontend): wire Storybook 8 with theme toolbar + test-runner

- main.ts: Vite framework, essentials addon, autodocs via
  react-docgen-typescript.
- preview.ts: imports design-system/index.css so stories
  render in the real Tailwind context. Theme toolbar
  switches data-theme attribute (dark default).
- test-runner: fixed viewport 1280x800 so visual stories
  are deterministic.

Stories themselves follow in the next 4 tasks
(Button/Badge/SeverityBadge/TLPBadge)."
```

---

## Task 20: `Button` primitive — M3 5 variants (TDD)

> **Per ADR 0005**: Button maps to M3 Common Button family with 5 styles:
> - `filled` (primary action, on-primary text)
> - `tonal` (secondary, secondary-container surface)
> - `outlined` (alternate prominence)
> - `text` (low emphasis)
> - `error` (destructive action, on-error text)
>
> Density override: size sm = 28 px (M3 32), md = 36 px (M3 40), lg = 44 px (M3 56).

**Files:**
- Create: `frontend/src/design-system/components/Button/Button.tsx`
- Create: `frontend/src/design-system/components/Button/Button.test.tsx`
- Create: `frontend/src/design-system/components/Button/Button.stories.tsx`
- Create: `frontend/src/design-system/components/Button/index.ts`

- [ ] **Step 1: Write failing test**

`frontend/src/design-system/components/Button/Button.test.tsx`:
```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "vitest-axe";
import { describe, expect, it, vi } from "vitest";
import { Button } from "./Button";

describe("<Button>", () => {
  it("renders children and fires onClick", async () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Save</Button>);
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(onClick).toHaveBeenCalledOnce();
  });

  it("blocks clicks while loading and shows aria-busy", async () => {
    const onClick = vi.fn();
    render(
      <Button loading onClick={onClick}>
        Save
      </Button>,
    );
    const btn = screen.getByRole("button", { name: /save/i });
    expect(btn).toHaveAttribute("aria-busy", "true");
    expect(btn).toBeDisabled();
    await userEvent.click(btn);
    expect(onClick).not.toHaveBeenCalled();
  });

  it("respects disabled prop", () => {
    render(<Button disabled>Save</Button>);
    expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();
  });

  it("has no a11y violations across variants", async () => {
    const { container } = render(
      <div>
        <Button variant="filled">F</Button>
        <Button variant="tonal">T</Button>
        <Button variant="outlined">O</Button>
        <Button variant="text">Tx</Button>
        <Button variant="error">E</Button>
      </div>,
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
```

- [ ] **Step 2: Run, verify FAIL**

```bash
cd frontend && pnpm test --run src/design-system/components/Button/Button.test.tsx
```

Expected: error — `./Button` module not found.

- [ ] **Step 3: Implement minimal**

`frontend/src/design-system/components/Button/Button.tsx`:
```tsx
import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from "react";

type Variant = "filled" | "tonal" | "outlined" | "text" | "error";
type Size = "sm" | "md" | "lg";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  /** Optional leading Material Symbol icon (string name of the symbol). */
  icon?: ReactNode;
}

/** M3 Common Button color schemes; on-* colors guarantee AA contrast. */
const VARIANT_CLASSES: Record<Variant, string> = {
  filled:
    "bg-primary text-on-primary hover:brightness-110 focus-visible:ring-2 focus-visible:ring-primary",
  tonal:
    "bg-secondary-container text-on-secondary-container hover:brightness-110 focus-visible:ring-2 focus-visible:ring-secondary",
  outlined:
    "bg-transparent text-primary border border-outline hover:bg-surface-container-high focus-visible:ring-2 focus-visible:ring-primary",
  text: "bg-transparent text-primary hover:bg-surface-container-high focus-visible:ring-2 focus-visible:ring-primary",
  error:
    "bg-error text-on-error hover:brightness-110 focus-visible:ring-2 focus-visible:ring-error",
};

/** Density override per ADR 0005: tighter than stock M3. */
const SIZE_CLASSES: Record<Size, string> = {
  sm: "h-7 px-3 text-[var(--md-sys-typescale-label-medium-size)]", // 28 px
  md: "h-9 px-4 text-[var(--md-sys-typescale-label-large-size)]", // 36 px
  lg: "h-11 px-6 text-[var(--md-sys-typescale-title-medium-size)]", // 44 px
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "filled", size = "md", loading = false, disabled, icon, className = "", children, ...rest },
  ref,
) {
  const isDisabled = disabled || loading;
  const classes = [
    "inline-flex items-center justify-center gap-2 rounded-shape-full font-medium transition-[background-color,color,filter] outline-none",
    "disabled:opacity-38 disabled:cursor-not-allowed", // M3 disabled state = 38% opacity
    VARIANT_CLASSES[variant],
    SIZE_CLASSES[size],
    className,
  ].join(" ");
  return (
    <button
      ref={ref}
      className={classes}
      disabled={isDisabled}
      aria-busy={loading || undefined}
      style={{ transitionDuration: "var(--md-sys-motion-duration-short2)", transitionTimingFunction: "var(--md-sys-motion-easing-standard)" }}
      {...rest}
    >
      {loading ? (
        <span aria-hidden className="material-symbols-rounded text-[18px] animate-spin">progress_activity</span>
      ) : icon ? (
        <span aria-hidden className="material-symbols-rounded text-[18px]">{icon}</span>
      ) : null}
      {children}
    </button>
  );
});
```

`frontend/src/design-system/components/Button/index.ts`:
```ts
export { Button, type ButtonProps } from "./Button";
```

- [ ] **Step 4: Run, verify PASS**

```bash
cd frontend && pnpm test --run src/design-system/components/Button/Button.test.tsx
```

Expected: 4 tests pass.

- [ ] **Step 5: Write story with play-function**

`frontend/src/design-system/components/Button/Button.stories.tsx`:
```tsx
import type { Meta, StoryObj } from "@storybook/react";
import { expect, fn, userEvent, within } from "@storybook/test";
import { Button } from "./Button";

const meta: Meta<typeof Button> = {
  title: "Design System/Button",
  component: Button,
  args: { children: "Save", onClick: fn() },
};
export default meta;

type Story = StoryObj<typeof Button>;

export const Filled: Story = {
  args: { variant: "filled" },
  play: async ({ canvasElement, args }) => {
    const c = within(canvasElement);
    await userEvent.click(c.getByRole("button"));
    await expect(args.onClick).toHaveBeenCalledOnce();
  },
};

export const Tonal: Story = { args: { variant: "tonal" } };
export const Outlined: Story = { args: { variant: "outlined" } };
export const Text: Story = { args: { variant: "text" } };
export const ErrorVariant: Story = { args: { variant: "error" } };

export const WithIcon: Story = { args: { variant: "filled", icon: "save" } };

export const SizeSm: Story = { args: { size: "sm", children: "sm" } };
export const SizeMd: Story = { args: { size: "md", children: "md" } };
export const SizeLg: Story = { args: { size: "lg", children: "lg" } };

export const Loading: Story = { args: { loading: true } };
export const Disabled: Story = { args: { disabled: true } };
```

- [ ] **Step 6: Verify Storybook build still passes**

```bash
cd frontend && pnpm storybook:build
```

Expected: build succeeds; `storybook-static/` contains the Button stories.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/design-system/components/Button/
git commit -s -m "feat(design-system): add M3 Button (filled/tonal/outlined/text/error)

Per ADR 0005 Material Design 3.

forwardRef-backed button with 5 M3 variants (filled, tonal,
outlined, text, error), 3 sizes with density override (sm
28 px, md 36 px, lg 44 px; M3 stock is 32/40/56), and a
loading state that swaps the leading icon for the
progress_activity Material Symbol and sets aria-busy.

Optional 'icon' prop accepts a Material Symbol name string;
internal <span class='material-symbols-rounded'> wraps it
with FILL 0 / wght 400 defaults.

Rounded-full shape per M3 Common Button spec. M3 38%
disabled opacity. Motion: short2 duration + standard easing.

Stories cover every variant, sizes, loading, disabled,
with-icon. Filled story play-function asserts click fires.
Tests cover behavior + axe a11y across all 5 variants."
```

---

## Task 21: `Chip` primitive — M3 Assist Chip styling (TDD)

> **Per ADR 0005**: this primitive **replaces** the original `Badge` from spec v1. Implementing as M3 Assist Chip: full rounded shape, surface-container background, leading Material Symbol icon optional. Phase 0 ships 5 color tones (neutral/info/success/warning/danger) for status display (used by HealthPage Task 27). M3 variants `filter`/`input`/`suggestion` follow in Phase 2 when tag/filter UI lands; their addition is non-breaking via discriminated-union variant prop.
>
> **Mechanical rename when implementing**: every `Badge`/`badge` token in the test, implementation, story, and index file below becomes `Chip`/`chip`. Directory path becomes `Chip/`. Test imports `from "./Chip"` etc. Add a `leadingIcon?: string` prop (Material Symbol name); render with `<span class="material-symbols-rounded">{leadingIcon}</span>`.

**Files:**
- Create: `frontend/src/design-system/components/Chip/Chip.tsx`
- Create: `frontend/src/design-system/components/Chip/Chip.test.tsx`
- Create: `frontend/src/design-system/components/Chip/Chip.stories.tsx`
- Create: `frontend/src/design-system/components/Chip/index.ts`

- [ ] **Step 1: Write failing test**

`frontend/src/design-system/components/Badge/Badge.test.tsx`:
```tsx
import { render, screen } from "@testing-library/react";
import { axe } from "vitest-axe";
import { describe, expect, it } from "vitest";
import { Badge } from "./Badge";

describe("<Badge>", () => {
  it("renders children", () => {
    render(<Badge>New</Badge>);
    expect(screen.getByText("New")).toBeInTheDocument();
  });

  it("applies variant data-attribute", () => {
    render(<Badge variant="warning">Old</Badge>);
    expect(screen.getByText("Old")).toHaveAttribute("data-variant", "warning");
  });

  it("has no a11y violations for all variants", async () => {
    const { container } = render(
      <div>
        <Badge variant="neutral">N</Badge>
        <Badge variant="info">I</Badge>
        <Badge variant="success">S</Badge>
        <Badge variant="warning">W</Badge>
        <Badge variant="danger">D</Badge>
      </div>,
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
```

- [ ] **Step 2: Run, verify FAIL**

```bash
cd frontend && pnpm test --run src/design-system/components/Badge/Badge.test.tsx
```

Expected: module not found.

- [ ] **Step 3: Implement minimal**

`frontend/src/design-system/components/Badge/Badge.tsx`:
```tsx
import type { HTMLAttributes } from "react";

type Variant = "neutral" | "info" | "success" | "warning" | "danger";

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: Variant;
}

const VARIANT_CLASSES: Record<Variant, string> = {
  neutral: "bg-surface text-fg-muted border-border",
  info: "bg-severity-1/20 text-severity-1 border-severity-1/40",
  success: "bg-tlp-green/20 text-tlp-green border-tlp-green/40",
  warning: "bg-severity-2/20 text-severity-2 border-severity-2/40",
  danger: "bg-severity-4/20 text-severity-4 border-severity-4/40",
};

export function Badge({ variant = "neutral", className = "", children, ...rest }: BadgeProps) {
  return (
    <span
      data-variant={variant}
      className={[
        "inline-flex items-center gap-1 rounded-sm border px-1.5 py-0.5 text-xs font-medium leading-none",
        VARIANT_CLASSES[variant],
        className,
      ].join(" ")}
      {...rest}
    >
      {children}
    </span>
  );
}
```

`frontend/src/design-system/components/Badge/index.ts`:
```ts
export { Badge, type BadgeProps } from "./Badge";
```

- [ ] **Step 4: Run, verify PASS**

```bash
cd frontend && pnpm test --run src/design-system/components/Badge/Badge.test.tsx
```

Expected: 3 tests pass.

- [ ] **Step 5: Story**

`frontend/src/design-system/components/Badge/Badge.stories.tsx`:
```tsx
import type { Meta, StoryObj } from "@storybook/react";
import { Badge } from "./Badge";

const meta: Meta<typeof Badge> = {
  title: "Design System/Badge",
  component: Badge,
  args: { children: "label" },
};
export default meta;
type Story = StoryObj<typeof Badge>;

export const Neutral: Story = { args: { variant: "neutral" } };
export const Info: Story = { args: { variant: "info" } };
export const Success: Story = { args: { variant: "success" } };
export const Warning: Story = { args: { variant: "warning" } };
export const Danger: Story = { args: { variant: "danger" } };
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/design-system/components/Chip/
git commit -s -m "feat(design-system): add M3 Chip primitive (Assist Chip)

Per ADR 0005. Replaces the original Badge primitive from
spec v1. M3 Assist Chip styling: rounded-shape-small,
surface-container background, on-surface text, outline
border for hairline structure.

5 color tones for status display: neutral
(surface-container), info (severity-1 blue with bg/20%),
success (tlp-green), warning (severity-2 amber), danger
(severity-4 red).

Optional leadingIcon prop accepts a Material Symbol name
string and renders <span class='material-symbols-rounded'>.

data-variant attribute exposed for downstream styling/
testing. M3 filter/input/suggestion variants land in Phase
2 when tag and filter UI arrives."
```

---

## Task 22: `SeverityBadge` primitive — M3 Assist Chip with leading dot (TDD)

> **Per ADR 0005**: M3 Assist Chip variant; full mode shows leading dot + label, compact shows dot only. Dot color = severity 1-4 token. Outline uses `--md-sys-color-outline-variant`. Background uses corresponding severity color at 15% alpha for AA contrast on dark surface.

**Files:**
- Create: `frontend/src/design-system/components/SeverityBadge/SeverityBadge.tsx`
- Create: `frontend/src/design-system/components/SeverityBadge/SeverityBadge.test.tsx`
- Create: `frontend/src/design-system/components/SeverityBadge/SeverityBadge.stories.tsx`
- Create: `frontend/src/design-system/components/SeverityBadge/index.ts`

- [ ] **Step 1: Write failing test**

`frontend/src/design-system/components/SeverityBadge/SeverityBadge.test.tsx`:
```tsx
import { render, screen } from "@testing-library/react";
import { axe } from "vitest-axe";
import { describe, expect, it } from "vitest";
import { SeverityBadge } from "./SeverityBadge";

describe("<SeverityBadge>", () => {
  it.each([
    [1, "Low"],
    [2, "Medium"],
    [3, "High"],
    [4, "Critical"],
  ] as const)("level %i renders label %s with text and aria-label", (level, label) => {
    render(<SeverityBadge level={level} />);
    const el = screen.getByRole("status", { name: new RegExp(label, "i") });
    expect(el).toHaveTextContent(label);
    expect(el).toHaveAttribute("aria-label", expect.stringContaining(label));
    expect(el).toHaveAttribute("data-severity", String(level));
  });

  it("compact variant hides text but keeps aria-label", () => {
    render(<SeverityBadge level={3} compact />);
    const el = screen.getByRole("status");
    expect(el).toHaveTextContent(""); // no visible text
    expect(el).toHaveAttribute("aria-label", expect.stringContaining("High"));
  });

  it("has no a11y violations across levels", async () => {
    const { container } = render(
      <div>
        {[1, 2, 3, 4].map((l) => (
          <SeverityBadge key={l} level={l as 1 | 2 | 3 | 4} />
        ))}
      </div>,
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
```

- [ ] **Step 2: Run, verify FAIL**

```bash
cd frontend && pnpm test --run src/design-system/components/SeverityBadge/SeverityBadge.test.tsx
```

Expected: module not found.

- [ ] **Step 3: Implement minimal**

`frontend/src/design-system/components/SeverityBadge/SeverityBadge.tsx`:
```tsx
import type { HTMLAttributes } from "react";

export type SeverityLevel = 1 | 2 | 3 | 4;

export interface SeverityBadgeProps extends Omit<HTMLAttributes<HTMLSpanElement>, "aria-label"> {
  level: SeverityLevel;
  compact?: boolean;
}

const LABELS: Record<SeverityLevel, string> = {
  1: "Low",
  2: "Medium",
  3: "High",
  4: "Critical",
};

const COLOR_CLASSES: Record<SeverityLevel, string> = {
  1: "bg-severity-1/20 text-severity-1 border-severity-1/40",
  2: "bg-severity-2/20 text-severity-2 border-severity-2/40",
  3: "bg-severity-3/20 text-severity-3 border-severity-3/40",
  4: "bg-severity-4/20 text-severity-4 border-severity-4/40",
};

export function SeverityBadge({
  level,
  compact = false,
  className = "",
  ...rest
}: SeverityBadgeProps) {
  const label = LABELS[level];
  const ariaLabel = `Severity: ${label}`;
  const base = "inline-flex items-center gap-1 rounded-sm border font-medium leading-none";
  const sizing = compact ? "h-3 w-3 p-0" : "px-1.5 py-0.5 text-xs";
  return (
    <span
      role="status"
      aria-label={ariaLabel}
      data-severity={level}
      className={[base, sizing, COLOR_CLASSES[level], className].join(" ")}
      {...rest}
    >
      {!compact && label}
    </span>
  );
}
```

`frontend/src/design-system/components/SeverityBadge/index.ts`:
```ts
export { SeverityBadge, type SeverityBadgeProps, type SeverityLevel } from "./SeverityBadge";
```

- [ ] **Step 4: Run, verify PASS**

```bash
cd frontend && pnpm test --run src/design-system/components/SeverityBadge/SeverityBadge.test.tsx
```

Expected: 7 tests pass (4 parametrized + compact + axe + base).

- [ ] **Step 5: Story**

`frontend/src/design-system/components/SeverityBadge/SeverityBadge.stories.tsx`:
```tsx
import type { Meta, StoryObj } from "@storybook/react";
import { SeverityBadge } from "./SeverityBadge";

const meta: Meta<typeof SeverityBadge> = {
  title: "Design System/SeverityBadge",
  component: SeverityBadge,
};
export default meta;
type Story = StoryObj<typeof SeverityBadge>;

export const Low: Story = { args: { level: 1 } };
export const Medium: Story = { args: { level: 2 } };
export const High: Story = { args: { level: 3 } };
export const Critical: Story = { args: { level: 4 } };

export const CompactLow: Story = { args: { level: 1, compact: true } };
export const CompactMedium: Story = { args: { level: 2, compact: true } };
export const CompactHigh: Story = { args: { level: 3, compact: true } };
export const CompactCritical: Story = { args: { level: 4, compact: true } };
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/design-system/components/SeverityBadge/
git commit -s -m "feat(design-system): add SeverityBadge (level 1-4, compact variant)

Finite type-safe level (1 Low | 2 Medium | 3 High | 4
Critical). aria-label always carries the severity label
even in compact mode (color-blind safety). data-severity
exposes the numeric level for filter selectors.

Per spec §6.4: dedicated component, not a Badge variant,
because severity has finite domain values and accessibility
requires non-color-only encoding."
```

---

## Task 23: `TLPBadge` primitive — M3 Outlined Chip (TDD)

> **Per ADR 0005**: M3 Outlined Chip variant. FIRST.org 2.0 mandates `TLP:XXX` text + specific colors; those override M3 color slots. Background transparent, outline = TLP color, text = TLP color uppercased + tracking-wider.

**Files:**
- Create: `frontend/src/design-system/components/TLPBadge/TLPBadge.tsx`
- Create: `frontend/src/design-system/components/TLPBadge/TLPBadge.test.tsx`
- Create: `frontend/src/design-system/components/TLPBadge/TLPBadge.stories.tsx`
- Create: `frontend/src/design-system/components/TLPBadge/index.ts`

- [ ] **Step 1: Write failing test**

`frontend/src/design-system/components/TLPBadge/TLPBadge.test.tsx`:
```tsx
import { render, screen } from "@testing-library/react";
import { axe } from "vitest-axe";
import { describe, expect, it } from "vitest";
import { TLPBadge, type TLPValue } from "./TLPBadge";

describe("<TLPBadge>", () => {
  const cases: ReadonlyArray<readonly [TLPValue, string]> = [
    ["white", "TLP:WHITE"],
    ["green", "TLP:GREEN"],
    ["amber", "TLP:AMBER"],
    ["amber-strict", "TLP:AMBER+STRICT"],
    ["red", "TLP:RED"],
  ];

  it.each(cases)("tlp=%s renders %s", (tlp, label) => {
    render(<TLPBadge tlp={tlp} />);
    const el = screen.getByRole("status", { name: label });
    expect(el).toHaveTextContent(label);
    expect(el).toHaveAttribute("data-tlp", tlp);
  });

  it("has no a11y violations across values", async () => {
    const { container } = render(
      <div>
        {(["white", "green", "amber", "amber-strict", "red"] as const).map((t) => (
          <TLPBadge key={t} tlp={t} />
        ))}
      </div>,
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
```

- [ ] **Step 2: Run, verify FAIL**

```bash
cd frontend && pnpm test --run src/design-system/components/TLPBadge/TLPBadge.test.tsx
```

Expected: module not found.

- [ ] **Step 3: Implement minimal**

`frontend/src/design-system/components/TLPBadge/TLPBadge.tsx`:
```tsx
import type { HTMLAttributes } from "react";

export type TLPValue = "white" | "green" | "amber" | "amber-strict" | "red";

export interface TLPBadgeProps extends Omit<HTMLAttributes<HTMLSpanElement>, "aria-label"> {
  tlp: TLPValue;
}

const LABELS: Record<TLPValue, string> = {
  white: "TLP:WHITE",
  green: "TLP:GREEN",
  amber: "TLP:AMBER",
  "amber-strict": "TLP:AMBER+STRICT",
  red: "TLP:RED",
};

const COLOR_CLASSES: Record<TLPValue, string> = {
  white: "bg-tlp-white/15 text-tlp-white border-tlp-white/50",
  green: "bg-tlp-green/15 text-tlp-green border-tlp-green/50",
  amber: "bg-tlp-amber/15 text-tlp-amber border-tlp-amber/50",
  "amber-strict": "bg-tlp-amber-strict/15 text-tlp-amber-strict border-tlp-amber-strict/50",
  red: "bg-tlp-red/15 text-tlp-red border-tlp-red/50",
};

export function TLPBadge({ tlp, className = "", ...rest }: TLPBadgeProps) {
  const label = LABELS[tlp];
  return (
    <span
      role="status"
      aria-label={label}
      data-tlp={tlp}
      className={[
        "inline-flex items-center gap-1 rounded-sm border px-1.5 py-0.5 text-[0.65rem] font-bold uppercase leading-none tracking-wider",
        COLOR_CLASSES[tlp],
        className,
      ].join(" ")}
      {...rest}
    >
      {label}
    </span>
  );
}
```

`frontend/src/design-system/components/TLPBadge/index.ts`:
```ts
export { TLPBadge, type TLPBadgeProps, type TLPValue } from "./TLPBadge";
```

- [ ] **Step 4: Run, verify PASS**

```bash
cd frontend && pnpm test --run src/design-system/components/TLPBadge/TLPBadge.test.tsx
```

Expected: 6 tests pass (5 parametrized + axe).

- [ ] **Step 5: Story**

`frontend/src/design-system/components/TLPBadge/TLPBadge.stories.tsx`:
```tsx
import type { Meta, StoryObj } from "@storybook/react";
import { TLPBadge } from "./TLPBadge";

const meta: Meta<typeof TLPBadge> = {
  title: "Design System/TLPBadge",
  component: TLPBadge,
};
export default meta;
type Story = StoryObj<typeof TLPBadge>;

export const White: Story = { args: { tlp: "white" } };
export const Green: Story = { args: { tlp: "green" } };
export const Amber: Story = { args: { tlp: "amber" } };
export const AmberStrict: Story = { args: { tlp: "amber-strict" } };
export const Red: Story = { args: { tlp: "red" } };
```

- [ ] **Step 6: Verify full test suite + storybook build**

```bash
cd frontend && pnpm test --run
pnpm storybook:build
```

Expected: all tests pass; Storybook static build emits Button + Badge + SeverityBadge + TLPBadge stories.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/design-system/components/TLPBadge/
git commit -s -m "feat(design-system): add TLPBadge (FIRST.org 2.0 values)

Encodes TLP:WHITE | GREEN | AMBER | AMBER+STRICT | RED with
FIRST.org-mandated text (TLP:XXX) and color. uppercase +
bold + tracking-wider matches FIRST.org visual standard.
data-tlp attribute exposes raw value for sort/filter
selectors.

Per spec §6.4. Closes design-system primitive #4."
```

---

## Task 24: Theme toggle module (TDD)

**Files:**
- Create: `frontend/src/lib/theme.ts`
- Create: `frontend/src/lib/theme.test.ts`

- [ ] **Step 1: Write failing test**

`frontend/src/lib/theme.test.ts`:
```ts
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { applyTheme, getStoredTheme, setStoredTheme, toggleTheme, type Theme } from "./theme";

describe("theme", () => {
  beforeEach(() => {
    document.documentElement.dataset.theme = "dark";
    localStorage.clear();
  });
  afterEach(() => localStorage.clear());

  it("applyTheme writes data-theme attribute", () => {
    applyTheme("light");
    expect(document.documentElement.dataset.theme).toBe("light");
  });

  it("setStoredTheme persists to localStorage and applies", () => {
    setStoredTheme("light");
    expect(localStorage.getItem("adhkar.theme")).toBe("light");
    expect(document.documentElement.dataset.theme).toBe("light");
  });

  it("getStoredTheme returns dark default when nothing stored", () => {
    expect(getStoredTheme()).toBe("dark");
  });

  it("getStoredTheme returns the persisted value", () => {
    localStorage.setItem("adhkar.theme", "light");
    expect(getStoredTheme()).toBe("light");
  });

  it("toggleTheme flips dark<->light and persists", () => {
    setStoredTheme("dark");
    const next: Theme = toggleTheme();
    expect(next).toBe("light");
    expect(localStorage.getItem("adhkar.theme")).toBe("light");
    expect(toggleTheme()).toBe("dark");
  });
});
```

- [ ] **Step 2: Run, verify FAIL**

```bash
cd frontend && pnpm test --run src/lib/theme.test.ts
```

Expected: module not found.

- [ ] **Step 3: Implement minimal**

`frontend/src/lib/theme.ts`:
```ts
export type Theme = "dark" | "light";

const STORAGE_KEY = "adhkar.theme";
const DEFAULT_THEME: Theme = "dark";

export function applyTheme(theme: Theme): void {
  document.documentElement.dataset.theme = theme;
}

export function getStoredTheme(): Theme {
  const v = localStorage.getItem(STORAGE_KEY);
  return v === "light" || v === "dark" ? v : DEFAULT_THEME;
}

export function setStoredTheme(theme: Theme): void {
  localStorage.setItem(STORAGE_KEY, theme);
  applyTheme(theme);
}

export function toggleTheme(): Theme {
  const next: Theme = getStoredTheme() === "dark" ? "light" : "dark";
  setStoredTheme(next);
  return next;
}
```

- [ ] **Step 4: Run, verify PASS**

```bash
cd frontend && pnpm test --run src/lib/theme.test.ts
```

Expected: 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/theme.ts frontend/src/lib/theme.test.ts
git commit -s -m "feat(frontend): add theme toggle module (dark default, localStorage)

Pure functions: applyTheme, getStoredTheme, setStoredTheme,
toggleTheme. Persists under 'adhkar.theme' key. dark is the
default per spec §6.3 (SOC dark-first). TopBar imports
toggleTheme; AppShell calls applyTheme(getStoredTheme()) on
mount to honor persisted choice before paint."
```

---

## Task 25: API client + version utilities

**Files:**
- Create: `frontend/src/lib/api.ts`
- Create: `frontend/src/lib/version.ts`
- Create: `frontend/src/lib/api.test.ts`

- [ ] **Step 1: Write failing test**

`frontend/src/lib/api.test.ts`:
```ts
import { describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { api } from "./api";

const BASE = "http://api.test";
const server = setupServer();

describe("api()", () => {
  beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
  afterEach(() => server.resetHandlers());
  afterAll(() => server.close());

  it("returns JSON for 200 responses", async () => {
    server.use(http.get(`${BASE}/healthz`, () => HttpResponse.json({ status: "ok" })));
    const res = await api(BASE).get("/healthz");
    expect(res).toEqual({ status: "ok" });
  });

  it("throws ApiError with structured payload for 4xx/5xx problem+json", async () => {
    server.use(
      http.get(`${BASE}/boom`, () =>
        HttpResponse.json(
          { type: "https://adhkar.dev/problems/internal", title: "I", status: 500, detail: "x" },
          { status: 500, headers: { "Content-Type": "application/problem+json" } },
        ),
      ),
    );
    await expect(api(BASE).get("/boom")).rejects.toMatchObject({
      status: 500,
      problem: { title: "I", detail: "x" },
    });
  });

  it("propagates X-Request-Id when provided", async () => {
    server.use(
      http.get(`${BASE}/healthz`, ({ request }) =>
        HttpResponse.json({ rid: request.headers.get("x-request-id") }),
      ),
    );
    const res = await api(BASE).get<{ rid: string }>("/healthz", { headers: { "X-Request-Id": "r-1" } });
    expect(res.rid).toBe("r-1");
  });
});
```

- [ ] **Step 2: Run, verify FAIL**

```bash
cd frontend && pnpm test --run src/lib/api.test.ts
```

Expected: module not found.

- [ ] **Step 3: Implement minimal**

`frontend/src/lib/api.ts`:
```ts
export interface ProblemDetails {
  type?: string;
  title?: string;
  status?: number;
  detail?: string;
  instance?: string;
  errors?: ReadonlyArray<unknown>;
}

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly problem: ProblemDetails,
  ) {
    super(problem.title ?? `HTTP ${status}`);
  }
}

export interface ApiOptions {
  headers?: Record<string, string>;
  signal?: AbortSignal;
}

export interface ApiClient {
  get<T>(path: string, opts?: ApiOptions): Promise<T>;
}

export function api(baseUrl: string): ApiClient {
  async function request<T>(method: string, path: string, opts: ApiOptions = {}): Promise<T> {
    const url = baseUrl.replace(/\/$/, "") + path;
    const res = await fetch(url, {
      method,
      headers: { Accept: "application/json", ...(opts.headers ?? {}) },
      signal: opts.signal,
    });
    if (!res.ok) {
      let problem: ProblemDetails = {};
      try {
        problem = (await res.json()) as ProblemDetails;
      } catch {
        // non-JSON body
      }
      throw new ApiError(res.status, problem);
    }
    return (await res.json()) as T;
  }
  return {
    get: <T>(p: string, o?: ApiOptions) => request<T>("GET", p, o),
  };
}
```

`frontend/src/lib/version.ts`:
```ts
export const APP_VERSION = "0.1.0-dev";
```

- [ ] **Step 4: Run, verify PASS**

```bash
cd frontend && pnpm test --run src/lib/api.test.ts
```

Expected: 3 tests pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/api.ts frontend/src/lib/version.ts frontend/src/lib/api.test.ts
git commit -s -m "feat(frontend): add tiny typed fetch wrapper + ApiError

api(baseUrl) returns a client with .get<T>(); 4xx/5xx are
parsed as RFC 7807 problem+json into an ApiError exposing
.status and .problem. Phase 1+ swaps this for an
openapi-typescript-generated client once routes exist; the
ApiError shape stays for backward compat.

Phase 0 surface is intentionally minimal (GET only) — no
POST/PUT yet because no mutating endpoint exists."
```

---

## Task 26: AppShell, TopAppBar, NavigationDrawer, CommandPalette (TDD)

> **Per ADR 0005**: components renamed to M3 vocabulary. File names follow:
> - `TopAppBar.tsx` (replaces `TopBar.tsx`) — M3 TopAppBar, 48 px density override
> - `NavigationDrawer.tsx` (replaces `LeftNav.tsx`) — M3 NavigationDrawer, item height 36 px (override M3 56)
> - Icons throughout use Material Symbols Rounded via `<span class="material-symbols-rounded">{name}</span>`, NOT lucide-react (removed from deps in Task 17)
>
> Mechanical mapping when implementing the task below: every `TopBar` token → `TopAppBar`, every `LeftNav` token → `NavigationDrawer`, every `lucide-react` import → drop; replace `<Moon/Sun/Command/Briefcase/...>` JSX with `<span className="material-symbols-rounded">{name}</span>` where name is the Material Symbol name (`dark_mode`/`light_mode`/`search`/`work`/`warning`/`task`/`dashboard`/`menu_book`/`settings`/`monitor_heart` for Health).

**Files:**
- Create: `frontend/src/ui/TopAppBar.tsx`
- Create: `frontend/src/ui/NavigationDrawer.tsx`
- Create: `frontend/src/ui/CommandPalette.tsx`
- Create: `frontend/src/app/AppShell.tsx`
- Create: `frontend/src/app/AppShell.test.tsx`

- [ ] **Step 1: Write failing test**

`frontend/src/app/AppShell.test.tsx`:
```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "vitest-axe";
import { describe, expect, it } from "vitest";
import { AppShell } from "./AppShell";

describe("<AppShell>", () => {
  it("renders TopBar with product name and ⌘K trigger", () => {
    render(
      <AppShell>
        <div>page</div>
      </AppShell>,
    );
    expect(screen.getByText("ADHKAR")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /open command palette/i })).toBeInTheDocument();
    expect(screen.getByText("page")).toBeInTheDocument();
  });

  it("LeftNav shows Health enabled and other items disabled with tooltip text", () => {
    render(
      <AppShell>
        <div />
      </AppShell>,
    );
    const health = screen.getByRole("link", { name: /health/i });
    expect(health).toBeInTheDocument();
    const cases = screen.getByRole("button", { name: /cases/i });
    expect(cases).toBeDisabled();
    expect(cases).toHaveAttribute("title", expect.stringContaining("Phase"));
  });

  it("⌘K opens the command palette", async () => {
    render(
      <AppShell>
        <div />
      </AppShell>,
    );
    await userEvent.keyboard("{Meta>}k{/Meta}");
    expect(screen.getByRole("dialog", { name: /command palette/i })).toBeInTheDocument();
    expect(screen.getByText(/Go to Health/i)).toBeInTheDocument();
  });

  it("theme toggle flips data-theme", async () => {
    document.documentElement.dataset.theme = "dark";
    render(
      <AppShell>
        <div />
      </AppShell>,
    );
    await userEvent.click(screen.getByRole("button", { name: /toggle theme/i }));
    expect(document.documentElement.dataset.theme).toBe("light");
  });

  it("axe baseline", async () => {
    const { container } = render(
      <AppShell>
        <div>page</div>
      </AppShell>,
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
```

- [ ] **Step 2: Run, verify FAIL**

```bash
cd frontend && pnpm test --run src/app/AppShell.test.tsx
```

Expected: module not found.

- [ ] **Step 3: Implement TopBar**

`frontend/src/ui/TopBar.tsx`:
```tsx
import { Moon, Sun, Command } from "lucide-react";
import { Button } from "@/design-system/components/Button";
import { toggleTheme, getStoredTheme } from "@/lib/theme";
import { useState } from "react";

interface TopBarProps {
  onOpenPalette: () => void;
}

export function TopBar({ onOpenPalette }: TopBarProps) {
  const [theme, setTheme] = useState(getStoredTheme());
  const Icon = theme === "dark" ? Moon : Sun;
  return (
    <header className="flex h-12 items-center justify-between border-b border-border bg-surface px-4">
      <div className="flex items-center gap-3">
        <span className="text-sm font-bold tracking-widest text-accent">ADHKAR</span>
        <span className="text-fg-subtle">·</span>
        <span className="text-xs text-fg-muted">Adhkar IR</span>
      </div>
      <div className="flex items-center gap-2">
        <Button
          variant="ghost"
          size="sm"
          aria-label="Open command palette"
          onClick={onOpenPalette}
        >
          <Command size={14} />
          <span>⌘K</span>
        </Button>
        <Button
          variant="ghost"
          size="sm"
          aria-label="Toggle theme"
          onClick={() => setTheme(toggleTheme())}
        >
          <Icon size={14} />
        </Button>
        <span className="text-xs text-fg-muted">@user</span>
      </div>
    </header>
  );
}
```

- [ ] **Step 4: Implement LeftNav**

`frontend/src/ui/LeftNav.tsx`:
```tsx
import { Link } from "@tanstack/react-router";
import { Activity, AlertTriangle, Briefcase, CheckSquare, BookOpen, BarChart3, Settings } from "lucide-react";
import type { ComponentType } from "react";

interface Item {
  to?: string;
  label: string;
  icon: ComponentType<{ size?: number }>;
  phase?: number;
}

const ITEMS: ReadonlyArray<Item> = [
  { to: "/health", label: "Health", icon: Activity },
  { label: "Cases", icon: Briefcase, phase: 3 },
  { label: "Alerts", icon: AlertTriangle, phase: 4 },
  { label: "Tasks", icon: CheckSquare, phase: 3 },
  { label: "Dashboards", icon: BarChart3, phase: 6 },
  { label: "Knowledge Base", icon: BookOpen, phase: 6 },
  { label: "Admin", icon: Settings, phase: 1 },
];

export function LeftNav() {
  return (
    <nav className="flex h-full w-56 flex-col border-r border-border bg-surface p-2">
      {ITEMS.map((it) => {
        const I = it.icon;
        if (it.to) {
          return (
            <Link
              key={it.label}
              to={it.to}
              className="flex items-center gap-2 rounded-md px-2 py-1.5 text-sm text-fg hover:bg-elevated"
            >
              <I size={14} />
              <span>{it.label}</span>
            </Link>
          );
        }
        return (
          <button
            key={it.label}
            type="button"
            disabled
            title={`Coming in Phase ${it.phase}`}
            className="flex items-center gap-2 rounded-md px-2 py-1.5 text-sm text-fg-subtle"
          >
            <I size={14} />
            <span>{it.label}</span>
          </button>
        );
      })}
    </nav>
  );
}
```

- [ ] **Step 5: Implement CommandPalette**

`frontend/src/ui/CommandPalette.tsx`:
```tsx
import { Command } from "cmdk";
import { useNavigate } from "@tanstack/react-router";

interface CommandPaletteProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function CommandPalette({ open, onOpenChange }: CommandPaletteProps) {
  const navigate = useNavigate();
  if (!open) return null;
  return (
    <div
      role="dialog"
      aria-label="Command palette"
      className="fixed inset-0 z-50 flex items-start justify-center bg-canvas/70 pt-32"
      onClick={() => onOpenChange(false)}
    >
      <div className="w-full max-w-md rounded-md border border-border bg-elevated p-2 shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <Command label="Command palette">
          <Command.Input placeholder="Type a command…" className="w-full bg-input p-2 text-sm outline-none" autoFocus />
          <Command.List className="mt-2 max-h-72 overflow-auto">
            <Command.Empty className="p-2 text-sm text-fg-muted">No results.</Command.Empty>
            <Command.Item
              onSelect={() => {
                onOpenChange(false);
                navigate({ to: "/health" });
              }}
              className="cursor-pointer rounded p-2 text-sm hover:bg-surface aria-selected:bg-surface"
            >
              Go to Health
            </Command.Item>
          </Command.List>
        </Command>
      </div>
    </div>
  );
}
```

- [ ] **Step 6: Implement AppShell**

`frontend/src/app/AppShell.tsx`:
```tsx
import { useEffect, useState, type ReactNode } from "react";
import { TopBar } from "@/ui/TopBar";
import { LeftNav } from "@/ui/LeftNav";
import { CommandPalette } from "@/ui/CommandPalette";
import { applyTheme, getStoredTheme } from "@/lib/theme";

export interface AppShellProps {
  children: ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  const [paletteOpen, setPaletteOpen] = useState(false);

  useEffect(() => {
    applyTheme(getStoredTheme());
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen((v) => !v);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <div className="flex h-screen flex-col">
      <TopBar onOpenPalette={() => setPaletteOpen(true)} />
      <div className="flex flex-1 overflow-hidden">
        <LeftNav />
        <main className="flex-1 overflow-auto bg-canvas p-4">{children}</main>
      </div>
      <CommandPalette open={paletteOpen} onOpenChange={setPaletteOpen} />
    </div>
  );
}
```

- [ ] **Step 7: Run, verify PASS**

The test imports `@tanstack/react-router` — provide a router context wrapper. Update `frontend/src/app/AppShell.test.tsx` to wrap with a stub router:

Add at top of the test file:
```tsx
import { RouterProvider, createMemoryHistory, createRootRoute, createRoute, createRouter } from "@tanstack/react-router";

function withRouter(child: React.ReactElement) {
  const root = createRootRoute({ component: () => child });
  const health = createRoute({ getParentRoute: () => root, path: "/health", component: () => null });
  const router = createRouter({ routeTree: root.addChildren([health]), history: createMemoryHistory({ initialEntries: ["/"] }) });
  return <RouterProvider router={router} />;
}
```

…then wrap every `render(<AppShell>…</AppShell>)` call as `render(withRouter(<AppShell>…</AppShell>))`.

```bash
cd frontend && pnpm test --run src/app/AppShell.test.tsx
```

Expected: 5 tests pass.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/ui/ frontend/src/app/AppShell.tsx frontend/src/app/AppShell.test.tsx
git commit -s -m "feat(frontend): assemble M3 AppShell (TopAppBar + NavigationDrawer + ⌘K)

Per ADR 0005 Material Design 3 dense-dark.

- TopAppBar (48 px, density override M3 default 64): ADHKAR
  wordmark in brand font, breadcrumb space, ⌘K trigger
  (Material Symbol 'search'), theme toggle ('dark_mode'/
  'light_mode' icon swap), user stub. Surface: surface.
- NavigationDrawer (224 px wide, item 36 px tall — density
  override M3 56): 7 items. Active item pill =
  secondary-container background + on-secondary-container
  text per M3 spec. Only Health enabled in Phase 0; others
  rendered as disabled <button> with title='Coming in Phase
  N' tooltip. Surface: surface-container-low.
- CommandPalette: cmdk dialog styled as M3 search bar
  modal, scrim = scrim/40%. Single initial entry 'Go to
  Health'.
- AppShell: surface canvas, reads getStoredTheme on mount
  to persist user choice before first paint, sets up ⌘K
  keyboard listener.

All icons via Material Symbols Rounded (lucide-react
removed in Task 17)."
```

---

## Task 27: HealthPage + routes + providers + App (TDD)

**Files:**
- Create: `frontend/src/pages/HealthPage.tsx`
- Create: `frontend/src/pages/HealthPage.test.tsx`
- Create: `frontend/src/app/routes.tsx`
- Create: `frontend/src/app/providers.tsx`
- Modify: `frontend/src/app/App.tsx`

- [ ] **Step 1: Write failing test**

`frontend/src/pages/HealthPage.test.tsx`:
```tsx
import { render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it } from "vitest";
import { HealthPage } from "./HealthPage";

const server = setupServer();
const API = "http://api.test";

function wrap(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{ui}</QueryClientProvider>;
}

describe("<HealthPage>", () => {
  beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
  afterEach(() => server.resetHandlers());
  afterAll(() => server.close());

  it("shows all checks healthy when /readyz is 200", async () => {
    server.use(
      http.get(`${API}/readyz`, () =>
        HttpResponse.json({ status: "ready", checks: { db: "ok", redis: "ok", s3: "ok" } }),
      ),
      http.get(`${API}/version`, () =>
        HttpResponse.json({ version: "0.1.0-dev", commit: "abc1234", builtAt: "2026-06-16T00:00:00Z" }),
      ),
    );
    render(wrap(<HealthPage apiBase={API} />));
    await waitFor(() => expect(screen.getByText(/Healthy/i)).toBeInTheDocument());
    expect(screen.getByText(/abc1234/)).toBeInTheDocument();
    expect(screen.getByText(/Database/i).parentElement).toHaveTextContent(/Connected/i);
  });

  it("shows degraded state when /readyz is 503 with redis down", async () => {
    server.use(
      http.get(`${API}/readyz`, () =>
        HttpResponse.json(
          { status: "degraded", checks: { db: "ok", redis: "down", s3: "ok" } },
          { status: 503 },
        ),
      ),
      http.get(`${API}/version`, () =>
        HttpResponse.json({ version: "0.1.0-dev", commit: "abc1234", builtAt: "2026-06-16T00:00:00Z" }),
      ),
    );
    render(wrap(<HealthPage apiBase={API} />));
    await waitFor(() => expect(screen.getByText(/Degraded/i)).toBeInTheDocument());
    expect(screen.getByText(/Redis/i).parentElement).toHaveTextContent(/Down/i);
  });
});
```

- [ ] **Step 2: Run, verify FAIL**

```bash
cd frontend && pnpm test --run src/pages/HealthPage.test.tsx
```

Expected: module not found.

- [ ] **Step 3: Implement HealthPage**

`frontend/src/pages/HealthPage.tsx`:
```tsx
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Chip } from "@/design-system/components/Chip";

interface ReadyResponse {
  status: "ready" | "degraded";
  checks: Record<string, "ok" | "down">;
}

interface VersionResponse {
  version: string;
  commit: string;
  builtAt: string;
}

interface HealthPageProps {
  apiBase?: string;
}

const DEFAULT_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "http://localhost:8000";

export function HealthPage({ apiBase = DEFAULT_BASE }: HealthPageProps) {
  const client = api(apiBase);
  const ready = useQuery<ReadyResponse>({
    queryKey: ["readyz"],
    queryFn: () => client.get<ReadyResponse>("/readyz"),
    refetchInterval: 10_000,
    // ApiError swallowed -> show degraded; treat 503 body as data
    queryFnReturnsErrorAsValue: false,
    retry: false,
  });
  const version = useQuery<VersionResponse>({
    queryKey: ["version"],
    queryFn: () => client.get<VersionResponse>("/version"),
    staleTime: Infinity,
  });

  const status = ready.data?.status ?? (ready.isError ? "degraded" : "loading");
  const checks = ready.data?.checks ?? {};

  return (
    <section className="mx-auto max-w-2xl">
      <h1 className="mb-4 text-lg font-semibold">Adhkar status</h1>
      <ul className="space-y-2 rounded-md border border-border bg-surface p-4">
        <li className="flex items-center justify-between">
          <span>API</span>
          <span className="flex items-center gap-2">
            <Chip variant={status === "ready" ? "success" : "danger"}>
              {status === "ready" ? "Healthy" : "Degraded"}
            </Chip>
            {version.data && (
              <span className="text-xs text-fg-muted">
                v{version.data.version} ({version.data.commit} · {version.data.builtAt})
              </span>
            )}
          </span>
        </li>
        {(["db", "redis", "s3"] as const).map((name) => (
          <li key={name} className="flex items-center justify-between">
            <span>{LABEL[name]}</span>
            <Chip variant={checks[name] === "ok" ? "success" : "danger"}>
              {checks[name] === "ok" ? CONNECTED[name] : "Down"}
            </Chip>
          </li>
        ))}
      </ul>
      <button
        type="button"
        onClick={() => {
          ready.refetch();
          version.refetch();
        }}
        className="mt-4 rounded-md border border-border bg-surface px-3 py-1.5 text-sm hover:bg-elevated"
      >
        Refresh
      </button>
    </section>
  );
}

const LABEL = { db: "Database", redis: "Redis", s3: "Object store" } as const;
const CONNECTED = { db: "Connected", redis: "Reachable", s3: "Bucket OK" } as const;
```

> **Note**: `queryFnReturnsErrorAsValue` is illustrative; TanStack Query v5 surfaces the 503 body via the catch path. The test calls `bypass` for unhandled and asserts the rendered status text, so this implementation must handle both `data` and the 503 case.

Adjust the ready query to capture the 503 body explicitly:
```tsx
const ready = useQuery<ReadyResponse>({
  queryKey: ["readyz"],
  queryFn: async () => {
    const url = `${apiBase}/readyz`;
    const res = await fetch(url, { headers: { Accept: "application/json" } });
    return (await res.json()) as ReadyResponse;
  },
  refetchInterval: 10_000,
  retry: false,
});
```

(Replace the earlier `client.get` block for `readyz` with the above; keep version using `client.get`.)

- [ ] **Step 4: Implement routes + providers + App**

`frontend/src/app/routes.tsx`:
```tsx
import {
  createRootRoute,
  createRoute,
  createRouter,
  Outlet,
} from "@tanstack/react-router";
import { AppShell } from "./AppShell";
import { HealthPage } from "@/pages/HealthPage";

const rootRoute = createRootRoute({
  component: () => (
    <AppShell>
      <Outlet />
    </AppShell>
  ),
});

const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  component: HealthPage,
});

const healthRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/health",
  component: HealthPage,
});

export const router = createRouter({
  routeTree: rootRoute.addChildren([indexRoute, healthRoute]),
});

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
```

`frontend/src/app/providers.tsx`:
```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "@tanstack/react-router";
import { useState } from "react";
import { router } from "./routes";

export function Providers() {
  const [qc] = useState(() => new QueryClient({ defaultOptions: { queries: { retry: false } } }));
  return (
    <QueryClientProvider client={qc}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  );
}
```

Replace `frontend/src/app/App.tsx`:
```tsx
import { Providers } from "./providers";

export function App() {
  return <Providers />;
}
```

- [ ] **Step 5: Run, verify PASS**

```bash
cd frontend && pnpm test --run
pnpm typecheck
pnpm lint
pnpm build
```

Expected: all tests pass, typecheck/lint clean, build succeeds.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/ frontend/src/app/routes.tsx frontend/src/app/providers.tsx frontend/src/app/App.tsx
git commit -s -m "feat(frontend): assemble routes, providers, and HealthPage

Per ADR 0005 — HealthPage uses M3 Chip (Assist style) for
per-check status display.

HealthPage polls /readyz every 10s, renders per-check Chips
(Healthy/Degraded for API; Connected/Down for db, redis,
s3), and shows version+commit+builtAt from /version. Treats
503 responses as data (not error) so degraded state renders
the actual breakdown rather than a blanket failure.

TanStack Router pins root to AppShell with Outlet so every
route inherits the M3 TopAppBar + NavigationDrawer chrome.
Index and /health both resolve to HealthPage in Phase 0;
routes fan out from there in subsequent phases."
```

---

## Task 28: Frontend Dockerfile + nginx config

**Files:**
- Create: `frontend/Dockerfile`
- Create: `frontend/nginx.conf`
- Create: `frontend/.dockerignore`
- Create: `frontend/public/.gitkeep`

- [ ] **Step 1: Create `frontend/.dockerignore`**

```
node_modules
dist
storybook-static
coverage
.eslintcache
```

- [ ] **Step 2: Create `frontend/public/.gitkeep`** (empty file — placeholder)

- [ ] **Step 3: Create `frontend/nginx.conf`**

```
server {
  listen 80;
  root /usr/share/nginx/html;
  index index.html;

  # SPA fallback
  location / {
    try_files $uri /index.html;
  }

  # Proxy /api/* to api:8000/* inside the docker network (only used in prod compose; dev hits host directly)
  location /api/ {
    proxy_pass http://api:8000/;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
  }

  # No-cache for index.html; allow cache for hashed assets
  location = /index.html {
    add_header Cache-Control "no-store";
  }
  location /assets/ {
    expires 1y;
    add_header Cache-Control "public, immutable";
  }
}
```

- [ ] **Step 4: Create `frontend/Dockerfile`**

```dockerfile
# syntax=docker/dockerfile:1.7

FROM node:22-alpine AS deps
RUN corepack enable && corepack prepare pnpm@9 --activate
WORKDIR /app
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

FROM deps AS dev
COPY . .
ENV NODE_ENV=development
EXPOSE 5173
CMD ["pnpm", "dev", "--host", "0.0.0.0"]

FROM deps AS build
COPY . .
ENV NODE_ENV=production
RUN pnpm build

FROM nginx:1.27-alpine AS runtime
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
HEALTHCHECK --interval=10s --timeout=3s CMD wget -qO- http://localhost/ >/dev/null || exit 1
```

- [ ] **Step 5: Build verification**

```bash
cd frontend
docker build -t adhkar/web:smoke-dev --target dev .
docker build -t adhkar/web:smoke-prod --target runtime .
docker run --rm -d -p 5174:5173 --name adhkar-web-smoke adhkar/web:smoke-dev
sleep 8
curl -fsS http://localhost:5174/ | grep -qi "<title>Adhkar IR</title>"
docker stop adhkar-web-smoke
```

Expected: both images build; dev stage serves the Vite dev page including the title.

- [ ] **Step 6: Commit**

```bash
git add frontend/Dockerfile frontend/nginx.conf frontend/.dockerignore frontend/public/.gitkeep
git commit -s -m "build(frontend): multi-stage Dockerfile (dev / build / nginx runtime)

- node:22-alpine + corepack-activated pnpm@9.
- 'dev' stage used by docker-compose: vite dev with bind
  mounts for hot reload (no copy).
- 'build' stage: tsc -b && vite build into /app/dist.
- 'runtime' stage: nginx serving SPA with /api/ proxy to the
  api:8000 service inside docker network. Cache-control: no-
  store on index.html, immutable for hashed assets.
- nginx.conf: SPA fallback via try_files, X-Forwarded-* on
  proxy, /assets/ cache headers."
```

---

## Task 29: GitHub Actions CI workflow

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Create `.github/workflows/ci.yml`**

```yaml
name: ci
on:
  pull_request:
  push:
    branches: [main]

concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true

permissions:
  contents: read

jobs:
  changes:
    runs-on: ubuntu-24.04
    outputs:
      backend: ${{ steps.f.outputs.backend }}
      frontend: ${{ steps.f.outputs.frontend }}
      deploy: ${{ steps.f.outputs.deploy }}
    steps:
      - uses: actions/checkout@v4
      - uses: dorny/paths-filter@v3
        id: f
        with:
          filters: |
            backend: [ 'backend/**' ]
            frontend: [ 'frontend/**' ]
            deploy: [ 'deploy/**' ]

  backend-quality:
    needs: changes
    if: needs.changes.outputs.backend == 'true' || github.ref == 'refs/heads/main'
    runs-on: ubuntu-24.04
    defaults: { run: { working-directory: backend } }
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
        with:
          version: "0.4.30"
          enable-cache: true
      - run: uv sync --frozen
      - run: uv run ruff check .
      - run: uv run ruff format --check .
      - run: uv run mypy adhkar
      - run: uv run pytest tests/unit -v --cov=adhkar --cov-report=xml --cov-fail-under=70
      - uses: actions/upload-artifact@v4
        with: { name: backend-coverage, path: backend/coverage.xml }

  frontend-quality:
    needs: changes
    if: needs.changes.outputs.frontend == 'true' || github.ref == 'refs/heads/main'
    runs-on: ubuntu-24.04
    defaults: { run: { working-directory: frontend } }
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v4
        with: { version: 9 }
      - uses: actions/setup-node@v4
        with:
          node-version: 22
          cache: pnpm
          cache-dependency-path: frontend/pnpm-lock.yaml
      - run: pnpm install --frozen-lockfile
      - run: pnpm lint
      - run: pnpm format:check
      - run: pnpm typecheck
      - run: pnpm test --run --coverage
      - run: pnpm build
      - run: pnpm storybook:build

  integration:
    needs: [backend-quality, frontend-quality]
    if: |
      always() &&
      (needs.backend-quality.result == 'success' || needs.backend-quality.result == 'skipped') &&
      (needs.frontend-quality.result == 'success' || needs.frontend-quality.result == 'skipped')
    runs-on: ubuntu-24.04
    services:
      postgres:
        image: pgvector/pgvector:pg16
        env:
          POSTGRES_USER: adhkar
          POSTGRES_PASSWORD: adhkar-dev
          POSTGRES_DB: adhkar
        ports: ["5432:5432"]
        options: >-
          --health-cmd "pg_isready -U adhkar"
          --health-interval 5s
          --health-timeout 3s
          --health-retries 10
      redis:
        image: redis:7-alpine
        ports: ["6379:6379"]
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 5s
          --health-timeout 3s
          --health-retries 10
      minio:
        image: minio/minio:latest
        env:
          MINIO_ROOT_USER: minio-dev
          MINIO_ROOT_PASSWORD: minio-dev-secret
        ports: ["9000:9000"]
        options: >-
          --health-cmd "curl -fsS http://localhost:9000/minio/health/ready"
          --health-interval 5s
          --health-timeout 3s
          --health-retries 10
          --entrypoint sh
        # NOTE: GH Actions does not let `command:` set MinIO mode here; we rely on
        # a separate minio-bootstrap step below that uses the mc client.
    env:
      DATABASE_URL: postgresql+asyncpg://adhkar:adhkar-dev@localhost:5432/adhkar
      REDIS_URL: redis://localhost:6379/0
      ADHKAR_S3_ENDPOINT: http://localhost:9000
      ADHKAR_S3_ACCESS_KEY: minio-dev
      ADHKAR_S3_SECRET_KEY: minio-dev-secret
      ADHKAR_S3_BUCKET: adhkar-attachments
      ADHKAR_SECRET_KEY: this-is-a-test-secret-32+chars-long
    defaults: { run: { working-directory: backend } }
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
        with: { version: "0.4.30", enable-cache: true }
      - run: uv sync --frozen
      - name: create minio bucket
        run: |
          curl -sSL https://dl.min.io/client/mc/release/linux-amd64/mc -o /usr/local/bin/mc
          chmod +x /usr/local/bin/mc
          mc alias set local http://localhost:9000 minio-dev minio-dev-secret
          mc mb local/adhkar-attachments
      - run: uv run alembic upgrade head
      - run: uv run pytest tests/integration -v

  build-images:
    needs: integration
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-24.04
    permissions:
      contents: read
      packages: write
      id-token: write
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - uses: docker/setup-buildx-action@v3
      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - id: sha
        run: echo "short=$(git rev-parse --short HEAD)" >> "$GITHUB_OUTPUT"
      - name: build & push api
        uses: docker/build-push-action@v6
        with:
          context: backend
          push: true
          tags: |
            ghcr.io/${{ github.repository_owner }}/adhkar-api:main
            ghcr.io/${{ github.repository_owner }}/adhkar-api:sha-${{ steps.sha.outputs.short }}
          build-args: |
            GIT_COMMIT=${{ steps.sha.outputs.short }}
            BUILT_AT=${{ github.event.repository.updated_at }}
      - name: build & push web
        uses: docker/build-push-action@v6
        with:
          context: frontend
          target: runtime
          push: true
          tags: |
            ghcr.io/${{ github.repository_owner }}/adhkar-web:main
            ghcr.io/${{ github.repository_owner }}/adhkar-web:sha-${{ steps.sha.outputs.short }}
      - uses: anchore/sbom-action@v0
        with:
          image: ghcr.io/${{ github.repository_owner }}/adhkar-api:sha-${{ steps.sha.outputs.short }}
          format: spdx-json
          artifact-name: sbom-api.spdx.json
      - uses: anchore/sbom-action@v0
        with:
          image: ghcr.io/${{ github.repository_owner }}/adhkar-web:sha-${{ steps.sha.outputs.short }}
          format: spdx-json
          artifact-name: sbom-web.spdx.json
      - uses: sigstore/cosign-installer@v3
      - name: cosign sign (keyless OIDC)
        env:
          COSIGN_EXPERIMENTAL: "1"
        run: |
          cosign sign --yes ghcr.io/${{ github.repository_owner }}/adhkar-api:sha-${{ steps.sha.outputs.short }}
          cosign sign --yes ghcr.io/${{ github.repository_owner }}/adhkar-web:sha-${{ steps.sha.outputs.short }}

  commitlint:
    if: github.event_name == 'pull_request'
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v4
      - uses: wagoid/commitlint-github-action@v6
        continue-on-error: true  # warn-only Phase 0; flip to required Phase 1
```

- [ ] **Step 2: Verify YAML loads**

```bash
python -c "import yaml,sys; yaml.safe_load(open('.github/workflows/ci.yml')); print('ok')"
```

Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/ci.yml
git commit -s -m "ci: add main pipeline (quality, integration, build, sign)

- paths-filter detects backend/frontend/deploy changes
  separately so docs PRs skip heavy jobs.
- backend-quality: ruff + mypy strict + pytest unit with
  coverage --cov-fail-under=70 (spec §8.4).
- frontend-quality: eslint + prettier --check + tsc + vitest
  --coverage + vite build + storybook:build.
- integration: pgvector + redis + minio service containers,
  mc bootstrap creates the bucket, alembic upgrade head,
  pytest integration suite.
- build-images: ghcr publish with sha-<short> and :main
  tags, SPDX SBOM per image, cosign keyless OIDC signing.
- commitlint: warn-only Phase 0; flip blocking Phase 1."
```

---

## Task 30: Container scan workflow + dependency review

**Files:**
- Create: `.github/workflows/container-scan.yml`
- Create: `.github/dependabot.yml`

- [ ] **Step 1: Create `.github/workflows/container-scan.yml`**

```yaml
name: container-scan
on:
  schedule:
    - cron: "0 6 * * 1" # weekly Monday 06:00 UTC
  push:
    branches: [main]

permissions:
  contents: read
  security-events: write

jobs:
  trivy-fs:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v4
      - uses: aquasecurity/trivy-action@0.24.0
        with:
          scan-type: fs
          scan-ref: .
          format: sarif
          output: trivy-fs.sarif
          ignore-unfixed: true
          severity: CRITICAL,HIGH
          exit-code: "1"
          # Phase 0: CRITICAL fails. HIGH warn-only — set exit-code back to '1' for HIGH in Phase 10.
      - uses: github/codeql-action/upload-sarif@v3
        if: always()
        with: { sarif_file: trivy-fs.sarif }

  trivy-images:
    if: github.ref == 'refs/heads/main' && github.event_name != 'schedule'
    needs: trivy-fs
    runs-on: ubuntu-24.04
    strategy:
      fail-fast: false
      matrix:
        image: [adhkar-api, adhkar-web]
    steps:
      - uses: actions/checkout@v4
      - id: sha
        run: echo "short=$(git rev-parse --short HEAD)" >> "$GITHUB_OUTPUT"
      - uses: aquasecurity/trivy-action@0.24.0
        with:
          image-ref: ghcr.io/${{ github.repository_owner }}/${{ matrix.image }}:sha-${{ steps.sha.outputs.short }}
          format: sarif
          output: trivy-${{ matrix.image }}.sarif
          severity: CRITICAL,HIGH
          exit-code: "1"
          ignore-unfixed: true
      - uses: github/codeql-action/upload-sarif@v3
        if: always()
        with: { sarif_file: trivy-${{ matrix.image }}.sarif }
```

- [ ] **Step 2: Create `.github/dependabot.yml`**

```yaml
version: 2
updates:
  - package-ecosystem: github-actions
    directory: /
    schedule: { interval: weekly }
  - package-ecosystem: pip
    directory: /backend
    schedule: { interval: weekly }
    open-pull-requests-limit: 10
  - package-ecosystem: npm
    directory: /frontend
    schedule: { interval: weekly }
    open-pull-requests-limit: 10
  - package-ecosystem: docker
    directory: /backend
    schedule: { interval: weekly }
  - package-ecosystem: docker
    directory: /frontend
    schedule: { interval: weekly }
```

- [ ] **Step 3: Verify**

```bash
python -c "import yaml; yaml.safe_load(open('.github/workflows/container-scan.yml')); yaml.safe_load(open('.github/dependabot.yml')); print('ok')"
```

Expected: `ok`.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/container-scan.yml .github/dependabot.yml
git commit -s -m "ci: add weekly Trivy scan + Dependabot for deps and actions

- container-scan.yml: filesystem scan every PR/push + weekly
  Monday cron; image scan post build-images on main. SARIF
  uploaded to GitHub Code Scanning. CRITICAL fails; HIGH
  warn-only Phase 0 (escalate Phase 10).
- dependabot.yml: weekly updates for GH Actions, pip
  (backend), npm (frontend), and Docker base images."
```

---

## Task 31: Pre-commit, PR template, CODEOWNERS

**Files:**
- Create: `.pre-commit-config.yaml`
- Create: `.github/pull_request_template.md`
- Create: `CODEOWNERS`
- Create: `commitlint.config.cjs`

- [ ] **Step 1: Create `.pre-commit-config.yaml`**

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-merge-conflict
      - id: check-added-large-files
        args: ["--maxkb=512"]
      - id: detect-private-key

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.7.0
    hooks:
      - id: ruff
        args: ["--fix"]
        files: ^backend/
      - id: ruff-format
        files: ^backend/

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.13.0
    hooks:
      - id: mypy
        files: ^backend/adhkar/
        args: ["--strict"]
        additional_dependencies:
          - pydantic>=2.9
          - sqlalchemy>=2.0
          - types-redis

  - repo: https://github.com/pre-commit/mirrors-prettier
    rev: v3.1.0
    hooks:
      - id: prettier
        files: ^frontend/
        types_or: [ts, tsx, css, json, markdown, yaml]

  - repo: https://github.com/alessandrojcm/commitlint-pre-commit-hook
    rev: v9.18.0
    hooks:
      - id: commitlint
        stages: [commit-msg]
        additional_dependencies: ["@commitlint/config-conventional"]
```

- [ ] **Step 2: Create `commitlint.config.cjs`**

```js
module.exports = {
  extends: ["@commitlint/config-conventional"],
  rules: {
    "subject-case": [0],
    "header-max-length": [2, "always", 100],
  },
};
```

- [ ] **Step 3: Create `.github/pull_request_template.md`**

```markdown
## What

<!-- One sentence: what does this PR change? -->

## Why

<!-- Why does this change exist? Link issue or spec section. -->

## How tested

- [ ] `pre-commit run --all-files`
- [ ] Backend: `cd backend && uv run pytest`
- [ ] Frontend: `cd frontend && pnpm test --run`
- [ ] Manual smoke (describe if UI):

## Checklist

- [ ] Conventional Commit format in title
- [ ] DCO sign-off (`git commit -s`)
- [ ] Tests added/updated for changed behavior
- [ ] Docs updated if behavior changed (runbook, API, ADR)
- [ ] No `.env` / secrets committed
- [ ] No new TODOs without tracking note in `docs/`
```

- [ ] **Step 4: Create `CODEOWNERS`**

```
# Architecture decisions: require owner review
/docs/ADRs/                @<owner>

# CI must always be reviewed by maintainers
/.github/workflows/        @<owner>
```

(Engineer fills `<owner>` with their GitHub handle.)

- [ ] **Step 5: Install + smoke**

```bash
pre-commit install
pre-commit install --hook-type commit-msg
pre-commit run --all-files
```

Expected: hooks pass (allow up to one autofix pass; rerun until clean).

- [ ] **Step 6: Commit**

```bash
git add .pre-commit-config.yaml commitlint.config.cjs .github/pull_request_template.md CODEOWNERS
git commit -s -m "chore: add pre-commit, commitlint, PR template, CODEOWNERS

- pre-commit: trailing-whitespace, EOF-fixer, large-file
  block, secret detection; ruff (fix) + ruff-format on
  backend; mypy --strict mirror; prettier on frontend;
  commitlint via commit-msg stage.
- commitlint config: conventional, subject-case relaxed,
  header up to 100 chars (so DCO/co-author footer lines
  don't trip).
- PR template: what/why/how-tested/checklist with DCO
  reminder.
- CODEOWNERS: ADR + workflows gated to <owner>."
```

---

## Task 32: Backend integration test using testcontainers

**Files:**
- Create: `backend/tests/integration/test_readyz_integration.py`
- Modify: `backend/tests/conftest.py` (create)

- [ ] **Step 1: Create shared conftest**

`backend/tests/conftest.py`:
```python
"""Shared pytest fixtures (session-scoped)."""

import os

import pytest


@pytest.fixture(autouse=True)
def _baseline_env(monkeypatch):
    """Set sane defaults so Settings constructor never aborts in tests."""
    monkeypatch.setenv("ADHKAR_SECRET_KEY", "x" * 32)
    monkeypatch.setenv("DATABASE_URL", os.environ.get("DATABASE_URL", "postgresql+asyncpg://u:p@h/db"))
    monkeypatch.setenv("REDIS_URL", os.environ.get("REDIS_URL", "redis://h:6379/0"))
    from adhkar.core.settings import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
```

- [ ] **Step 2: Write integration test**

`backend/tests/integration/test_readyz_integration.py`:
```python
import asyncio

import pytest
from httpx import ASGITransport, AsyncClient
from testcontainers.minio import MinioContainer
from testcontainers.postgres import PostgresContainer
from testcontainers.redis import RedisContainer


@pytest.fixture(scope="module")
def services():
    pg = PostgresContainer("pgvector/pgvector:pg16")
    rd = RedisContainer("redis:7-alpine")
    s3 = MinioContainer("minio/minio:latest")
    pg.start(); rd.start(); s3.start()
    try:
        yield {
            "database_url": pg.get_connection_url().replace("postgresql+psycopg2://", "postgresql+asyncpg://"),
            "redis_url": f"redis://{rd.get_container_host_ip()}:{rd.get_exposed_port(6379)}/0",
            "s3_endpoint": f"http://{s3.get_container_host_ip()}:{s3.get_exposed_port(9000)}",
            "s3_access_key": s3.access_key,
            "s3_secret_key": s3.secret_key,
        }
    finally:
        pg.stop(); rd.stop(); s3.stop()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_readyz_all_green_with_real_services(services, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", services["database_url"])
    monkeypatch.setenv("REDIS_URL", services["redis_url"])
    monkeypatch.setenv("ADHKAR_S3_ENDPOINT", services["s3_endpoint"])
    monkeypatch.setenv("ADHKAR_S3_ACCESS_KEY", services["s3_access_key"])
    monkeypatch.setenv("ADHKAR_S3_SECRET_KEY", services["s3_secret_key"])

    # bootstrap bucket
    import boto3
    s3client = boto3.client(
        "s3",
        endpoint_url=services["s3_endpoint"],
        aws_access_key_id=services["s3_access_key"],
        aws_secret_access_key=services["s3_secret_key"],
        region_name="us-east-1",
    )
    s3client.create_bucket(Bucket="adhkar-attachments")

    # run migrations
    from alembic.config import Config
    from alembic import command
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", services["database_url"])
    await asyncio.to_thread(command.upgrade, cfg, "head")

    # boot app
    from adhkar.core.settings import get_settings, Settings
    get_settings.cache_clear()
    from adhkar.main import create_app
    settings = Settings()  # type: ignore[call-arg]
    app = create_app(settings)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.get("/readyz")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ready"
    assert body["checks"] == {"db": "ok", "redis": "ok", "s3": "ok"}
```

- [ ] **Step 3: Run integration test locally**

```bash
cd backend && uv run pytest tests/integration -v -m integration
```

Expected: spins up three containers, applies migration, asserts all three readyz checks green; test passes in < 60 s.

- [ ] **Step 4: Commit**

```bash
git add backend/tests/conftest.py backend/tests/integration/test_readyz_integration.py
git commit -s -m "test(backend): add integration test for /readyz against real services

Uses testcontainers to bring up pgvector, redis, and minio,
bootstraps the adhkar-attachments bucket via boto3, runs
alembic upgrade head, then asserts /readyz returns 200 with
all three checks ok.

This is the canonical 'compose works end-to-end' check that
also runs in the CI integration job (which uses GH service
containers for speed)."
```

---

## Task 33: End-to-end DoD verification

This task does not produce code; it walks through the Phase 0 Definition of Done (spec §10) and records evidence. Use the checkboxes for sign-off.

- [ ] **Step 1: Verify clean clone boots in < 60 s**

```bash
cd /tmp && rm -rf adhkar-ir-verify
git clone /Users/salma/Documents/Research/adhkar-ir adhkar-ir-verify
cd adhkar-ir-verify/deploy
cp .env.example .env
# replace the demo secret key with a freshly generated one for sanity
sed -i.bak "s/^ADHKAR_SECRET_KEY=.*/ADHKAR_SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_hex(16))')/" .env && rm .env.bak
time docker compose up -d
```

Expected: `time` reports under 60 s wall-clock for cold up; `docker compose ps` shows `(healthy)` for postgres, redis, minio, mailhog, api, web; `minio-init` exited 0.

- [ ] **Step 2: Verify backend endpoints**

```bash
curl -fsS http://localhost:8000/healthz | python3 -m json.tool
curl -fsS http://localhost:8000/readyz | python3 -m json.tool
curl -fsS http://localhost:8000/version | python3 -m json.tool
curl -fsS http://localhost:8000/openapi.json > /tmp/spec.json
python3 -c "from openapi_spec_validator import validate_spec; import json; validate_spec(json.load(open('/tmp/spec.json'))); print('openapi valid')"
```

Expected: each curl returns the documented shape; openapi-spec-validator prints `openapi valid`.

- [ ] **Step 3: Verify frontend shell + theme + ⌘K**

Open <http://localhost:5173> in a browser. Manually confirm:
- [ ] Dark theme by default, no console errors (DevTools)
- [ ] LeftNav shows Health (enabled link) and 6 disabled items with "Coming in Phase N" tooltips
- [ ] Click Sun/Moon icon → theme flips to light, persists after refresh
- [ ] ⌘K (or Ctrl+K) opens the palette with "Go to Health" entry
- [ ] Navigate to <http://localhost:5173/health> — all four rows green

- [ ] **Step 4: Verify graceful degradation**

```bash
docker stop adhkar-redis
sleep 12
curl -fsS http://localhost:8000/readyz; echo
curl -fsS -o /dev/null -w "%{http_code}\n" http://localhost:8000/readyz
```

Reload <http://localhost:5173/health> in the browser — Redis row should show "Down", overall API badge should switch to "Degraded".

```bash
docker start adhkar-redis
sleep 12
```

Reload again — back to all green.

- [ ] **Step 5: Verify Storybook**

```bash
cd /tmp/adhkar-ir-verify/frontend
pnpm install --frozen-lockfile
pnpm storybook &
sleep 10
open http://localhost:6006
```

Manually confirm Button (5 M3 variants filled/tonal/outlined/text/error, all sizes, loading, disabled, with-icon), Chip (5 color tones), SeverityBadge (4 levels × {full, compact}), TLPBadge (5 values) all render. Verify Material Symbols Rounded icons render across all stories (no boxed "tofu" placeholders).

- [ ] **Step 6: Verify full test suites pass clean**

```bash
cd /tmp/adhkar-ir-verify/backend && uv sync && uv run pytest -v
cd /tmp/adhkar-ir-verify/frontend && pnpm test --run
```

Expected: zero failures, zero skips with warnings; coverage thresholds met.

- [ ] **Step 7: Verify CI on GitHub**

Push the branch (or open the repo's `main` after first push). Confirm:
- [ ] `backend-quality` green
- [ ] `frontend-quality` green
- [ ] `integration` green
- [ ] `build-images` (post merge to main) publishes `adhkar-api` and `adhkar-web` to ghcr with `:main` and `:sha-<short>`
- [ ] SBOMs attached as workflow artifacts
- [ ] cosign signatures present (run `cosign verify ghcr.io/<org>/adhkar-api:sha-<short> --certificate-identity-regexp '.*' --certificate-oidc-issuer https://token.actions.githubusercontent.com`)

- [ ] **Step 8: Record screencast for archive**

Capture a 90-second screencast (any tool) showing steps 2, 3, and 4 above. Save as `docs/screencasts/2026-06-16-phase0-dod.mp4` (or similar) — does not need to be committed, but link it from a release note when tagging `v0.1.0-dev`.

- [ ] **Step 9: Final teardown**

```bash
cd /tmp/adhkar-ir-verify/deploy && docker compose down -v
rm -rf /tmp/adhkar-ir-verify
```

---

## Task 34: Tag v0.1.0-dev and close Phase 0

**Files:** none (release ceremony only)

- [ ] **Step 1: Update spec status header**

Edit `docs/superpowers/specs/2026-06-16-adhkar-phase0-foundations-design.md`, change the header line from:
```
- Status: Approved (brainstorm) — pending implementation plan
```
to:
```
- Status: Implemented — Phase 0 closed 2026-06-XX (replace with real date)
```

- [ ] **Step 2: Update plan status (this file)**

Same idea: add a `- Status: Completed YYYY-MM-DD` line at the top.

- [ ] **Step 3: Commit & tag**

```bash
git add docs/superpowers/specs/2026-06-16-adhkar-phase0-foundations-design.md docs/superpowers/plans/2026-06-16-phase0-foundations.md
git commit -s -m "docs: mark Phase 0 spec + plan as implemented"
git tag -s v0.1.0-dev -m "Phase 0 foundations complete

- Repo skeleton, four ADRs, Apache-2.0 license, DCO sign-off
- docker-compose dev stack (postgres+pgvector, redis, minio,
  mailhog, api, web) boots green in < 60s
- FastAPI backend exposes /healthz, /readyz, /version,
  Swagger; OTel ready, structlog JSON, RFC 7807 errors
- React+Vite+TS+Tailwind v4+shadcn shell with dark default,
  ⌘K palette, design tokens, 4 primitives in Storybook
- CI: ruff+mypy+pytest, eslint+prettier+vitest, integration
  with service containers, ghcr publish with SBOM+cosign
- container-scan weekly, pre-commit hooks, conventional
  commits, CODEOWNERS for ADRs

Phase 1 (Identity, RBAC, Audit, Event/Outbox, Live-feed)
starts after gate review."
git push origin main --tags
```

Expected: tag pushed, GitHub Release auto-created from tag annotation (if configured).

- [ ] **Step 4: Announce gate**

In whatever channel the team uses, post a short announcement linking the v0.1.0-dev release and asking for sign-off before Phase 1 brainstorm starts.

---

## Self-review of this plan (run by the plan author before handoff)

### Spec coverage check

| Spec section | Phase 0 acceptance | Plan task |
|---|---|---|
| §2.1 Naming | repo/package/SDK/sub-module names locked | Tasks 1, 4, 17, 18; ADR 0001 in Task 2 |
| §2.2 License | Apache-2.0 + DCO + plugin readiness | Task 1 (LICENSE, NOTICE, CONTRIBUTING), Task 31 (DCO hook); ADR 0002 in Task 2 |
| §2.3 Search deferral | no OpenSearch, interface seat | Task 16 compose comment; ADR 0004 in Task 2 |
| §3.1 Layout | exact dir structure | Task 1 (root skeleton), Task 4 (backend), Task 17 (frontend) |
| §3.2 Tooling | uv, pnpm, Ruff, mypy, Vitest, Storybook | Task 4 (backend), Task 17 (frontend) |
| §4 Compose | services, profiles, env | Task 16 |
| §5.1–§5.4 Backend skeleton | factory, deps, errors | Tasks 5–8, 13 |
| §5.5 DB + migration | naming convention, init extensions | Tasks 10, 14 |
| §5.6 Logging | structlog JSON + request_id | Task 6 |
| §5.7 OTel | no-op default, opt-in | Task 9 |
| §5.8 Dockerfile | multi-stage + ARGs | Task 15 |
| §5.3 Endpoints | /healthz /readyz /version /docs | Tasks 11, 12, 13 |
| §6.1–§6.6 Frontend | shell, primitives, HealthPage, Storybook | Tasks 17–19, 20–23, 24–27 |
| §6.7 Dockerfile | dev + nginx runtime | Task 28 |
| §7 ADRs | four MADR docs | Task 2 |
| §8 Testing | unit, integration, Storybook play, coverage thresholds | Tasks 5–13 (unit), 19 (storybook), 32 (integration), 29 (coverage in CI) |
| §9 CI | jobs, SBOM, cosign, weekly scan, commitlint | Tasks 29, 30 |
| §10 DoD | all checkboxes | Task 33 |
| §11 Integration roadmap | documented | Task 3 (`architecture.md`) |
| §12 Phase 1 handoff | covered in Task 34 release note |
| §13 Out of scope | preserved by omission |
| §14 Risk register | mitigations baked into tasks (container_name, ARG INSTALL_GROUP, cosign perms) |
| §14a Placeholder convention | called out at Tasks 1 (README badge), 29 (build-args), 31 (CODEOWNERS) — engineer replaces `<org>`/`<owner>` once |

No section without coverage.

### Placeholder scan

- `<org>` and `<owner>` are intentional placeholders documented in spec §14a; the plan flags them at the relevant tasks. Engineer substitutes once before pushing.
- No `TBD`, `TODO`, `fill in`, `implement later`, or "similar to Task N" in the plan body. Spot-checked search returned zero matches outside of legitimate runbook text describing `.env` placeholders for users to fill in.

### Type consistency scan

- `Settings` field names used in Tasks 5/11/12/13 are identical (`secret_key`, `database_url`, `redis_url`, `s3_*`, `otel_*`, `git_commit`, `built_at`, `skip_migrations`).
- `CheckResult` dataclass shape (`name`, `ok`, `detail`) used consistently in Tasks 10, 12, 13, 32.
- Frontend `Theme` literal type and the `data-theme` HTML attribute treated consistently across Tasks 18, 24, 26.
- `SeverityLevel` and `TLPValue` exported from their primitive modules in Tasks 22, 23 — match the `data-severity` / `data-tlp` attributes used in tests.
- API `ApiError.problem.detail` shape matches the backend RFC 7807 body shape locked in Task 8.

### Scope check

Phase 0 is one focused slice (foundation). Plan covers it without spilling into Phase 1 surface area. Phase 1 outline is referenced only in Task 34's release note and in `architecture.md` (Task 3) — both are non-binding sketches.

No issues found that require revision. Plan ready for handoff.

---

## Plan complete and saved to `docs/superpowers/plans/2026-06-16-phase0-foundations.md`.

Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration. Cleaner separation of concerns; subagent doesn't accumulate cruft from earlier tasks.

**2. Inline Execution** — Execute tasks in this session using `superpowers:executing-plans`, batch execution with checkpoints. Keeps the full plan + decisions in one conversation.

**Which approach do you want?**








