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

Core repo `adhkar-ir` is Apache-2.0. Enterprise plugins live in a separate private repo `adhkar-enterprise` (created when first enterprise feature ships, paved Phase 7+) under commercial license. The core provides a **stable plugin interface** from Phase 1 so enterprise modules can drop in without forking.

### Positive Consequences
- Maximum adoption surface.
- DCO sign-off (`git commit -s`) is the only contributor friction — no CLA.
- No license-enforcement code in the core; enforcement is plugin-presence-based.

### Negative Consequences
- Forks may strip our brand; mitigated by trademark policy in NOTICE.
- Some "obvious" enterprise features (SSO, advanced multi-tenant quotas) live outside core, possibly confusing OSS users.

## Links

- See ADR 0001 (naming) and spec §2.2.
