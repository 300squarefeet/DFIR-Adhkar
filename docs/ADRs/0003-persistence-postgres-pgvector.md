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
