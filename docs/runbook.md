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
