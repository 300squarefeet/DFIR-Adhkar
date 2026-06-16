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
