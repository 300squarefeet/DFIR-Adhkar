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
