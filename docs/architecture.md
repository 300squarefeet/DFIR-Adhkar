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
- **Frontend**: Vite 5, React 18 + TypeScript, Tailwind v4, shadcn/Radix primitives on **Material Design 3 tokens** (Material Theme Builder + Material Symbols Rounded), TanStack Router/Query, Zustand, Storybook 8. See ADR 0005.
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
