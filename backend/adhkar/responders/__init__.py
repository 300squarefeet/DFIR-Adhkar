"""Responder plugins — destructive/state-changing actions on cases/observables.

Distinct from Analyzers (which are read-only enrichers). Every Responder
invocation is audit-logged and gated by manageResponder permission
(currently mapped to manageCase since that ships in Phase 1a)."""
