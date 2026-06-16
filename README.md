# Adhkar IR

> Open-source, self-hostable Security Incident Response Platform (SIRP) with a first-class AI layer.

<!-- TODO: replace <org> with the GitHub organization/username once the repo is provisioned (search-and-replace in README + NOTICE). -->
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

Full local stack ships in Phase 0 Task 16. See [`docs/superpowers/specs/`](docs/superpowers/specs/) for the design spec until then.

## Documentation

- Master spec: [`docs/superpowers/specs/`](docs/superpowers/specs/)
- Architecture Decision Records: [`docs/ADRs/`](docs/ADRs/)
- Architecture overview, runbook, and live API docs land in later Phase 0 tasks. Until then the master spec is canonical.

## License

Apache-2.0. See [`LICENSE`](LICENSE) and [`NOTICE`](NOTICE). Contributions require DCO sign-off — see [`CONTRIBUTING.md`](CONTRIBUTING.md).
