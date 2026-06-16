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
