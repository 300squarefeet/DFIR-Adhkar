# Adhkar IR — Data model

This document tracks the canonical entity model and relationships. It is **empty in Phase 0** — no domain entities exist yet.

## Phase 1 will introduce

- `Organization`, `User`, `UserOrgMembership`, `Profile`, `Permission`, `ApiKey`, `Session`, `MfaSecret`, `OrgSharing`, `AuditLog`, `OutboxEvent`

ERD diagram (mermaid) will land here at the end of Phase 1.

## Phase 2

- `Observable`, `ObservableType`, `AnalyzerJob`, `AnalyzerReport`, `Responder`, `ResponderAction`

## Conventions

All domain entities carry: `id` (UUID), `created_at`, `created_by`, `updated_at`, `updated_by`, `organization_id`, soft-delete flag where applicable, and emit `AuditLog` + `OutboxEvent` rows on mutation.
