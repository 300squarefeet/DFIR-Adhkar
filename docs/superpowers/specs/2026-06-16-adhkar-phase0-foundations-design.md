# Adhkar — Phase 0 Foundations (Design Spec)

- Status: Implemented — Phase 0 closed 2026-06-17
- Date: 2026-06-16
- Author: lead engineer (Adhkar)
- Scope: **Phase 0 only**. Phases 1–10 are scoped at a peek level (see §10) and will receive their own spec at their brainstorm gate.

---

## 1. Context

Adhkar adalah Security Incident Response Platform (SIRP) open-source self-hostable dengan target functional parity terhadap TheHive 5 Enterprise plus AI layer first-class. Lihat brief lengkap pemilik produk (mission statement, persona, feature checklist) sebagai dokumen induk — spec ini hanya membahas slice foundation (Phase 0).

Phase 0 tidak ada feature domain. Tujuannya tunggal: **membuktikan tulang punggung berdiri** (compose boots clean, CI green, design system tokens lock, app shell render dark theme) sehingga setiap phase berikutnya dapat menumpang infrastruktur yang sama tanpa rework.

---

## 2. Strategic decisions (locked during brainstorm)

Tiga keputusan strategis di-locked sebelum desain detail. Masing-masing akan diabadikan sebagai ADR di Phase 0 (lihat §7).

### 2.1 Naming — Adhkar

Nama produk **"TheBee"** yang diusulkan brief asli ditolak karena risiko trademark/dilution terhadap StrangeBee (pemilik TheHive) dan karena SDK `thebee4py`/`thebee4go` adalah mirror persis dari `thehive4py`/`thehive4go`. Diganti dengan **Adhkar**:

| Aspek | Nilai |
|---|---|
| Nama produk | Adhkar (long: "Adhkar IR" dalam prosa public-facing) |
| Repo | `adhkar-ir` |
| Package Python | `adhkar` |
| SDK | `adhkar-py` (Python), `adhkar-go` (Go) |
| Sub-modul | Adhkar Workers (analyzer/responder engine), Adhkar Mind (AI), Adhkar Portal (external collab) |
| CLI | `adhkarctl` |
| Container registry | `ghcr.io/<org>/adhkar-api`, `adhkar-web`, `adhkar-workers` |

### 2.2 License — Apache-2.0 core + commercial enterprise plugins (Grafana model)

Repo `adhkar-ir` ber-license **Apache-2.0**. Plugin enterprise hidup di repo private terpisah (`adhkar-enterprise`, dibuat paling cepat Phase 7) dengan commercial license. Phase 0 **tidak** membangun license-enforcement code; sebaliknya, Phase 1+ menyediakan stable plugin interface sehingga enterprise dapat drop-in tanpa fork.

Konsekuensi langsung Phase 0:
- File `LICENSE` (Apache-2.0), `NOTICE` (Adhkar trademark + Apache attribution).
- `CONTRIBUTING.md` mensyaratkan **DCO sign-off** (`-s`), bukan CLA.

### 2.3 Search — Postgres FTS dulu, OpenSearch ditunda

Spec asli mengusulkan OpenSearch dari Phase 0. Ditunda: PostgreSQL 16 punya `tsvector` + `pg_trgm` + GIN yang cukup untuk ratusan ribu observables sub-detik. OpenSearch tetap akan ditambahkan kalau-trigger-tercapai (lihat ADR 0004). Phase 0 melahirkan **`SearchIndex` interface** dengan `PostgresSearchIndex` impl di Phase 1.

### 2.4 UI design system — Material Design 3, dense + dark default

Setelah spec awal (yang memakai shadcn + custom token gaya SOC) di-approve, project lead meminta alignment ke Material Design 3 (referensi visual: produk Google modern). Pushback memilah dua varian M3: konsumer-style (Google Health: light, generous) vs. dense-dark-style (Tines, Hunters, GitHub Primer v15+). Pilihan: **dense dark M3-aligned**.

Implementasinya: M3 token system (Material Theme Builder), M3 shape system, M3 type scale, **Material Symbols Rounded** sebagai icon family, dan M3 button variants (filled / tonal / outlined / text / error). Dilayer di atas **Tailwind v4 + shadcn/Radix** (Radix memberi a11y dan keyboard nav yang Material Web belum match). Density override eksplisit (TopAppBar 48 px, nav item 36 px, list row 32 px), dark default, dan **domain color overrides**: severity 1–4 dan FIRST.org TLP white/green/amber/amber-strict/red mengalahkan M3 `error`/`warning`/`tertiary` slot di mana saja semantik domain ditampilkan. Detail lengkap di ADR 0005.

---

## 3. Repository layout & tooling

### 3.1 Direktori root

```
adhkar-ir/
├── backend/                 # FastAPI app (Python 3.12)
│   ├── adhkar/               # package: import path "adhkar.*"
│   │   ├── api/             # routers (v1/*.py), dependencies, errors
│   │   ├── core/            # settings, logging, otel bootstrap, middleware
│   │   ├── db/              # engine, session, base, readiness
│   │   └── main.py          # FastAPI factory
│   ├── alembic/             # env.py + versions/
│   ├── scripts/             # entrypoint.sh
│   ├── tests/               # pytest (unit/, integration/)
│   ├── pyproject.toml       # uv-managed
│   ├── uv.lock
│   └── Dockerfile
├── frontend/                # Vite + React 18 + TS
│   ├── src/
│   │   ├── app/             # router, AppShell, providers
│   │   ├── pages/           # HealthPage.tsx
│   │   ├── design-system/   # tokens.css, tailwind.config.ts, components/
│   │   ├── ui/              # TopBar, LeftNav, CommandPalette
│   │   └── lib/             # api wrapper, theme, version
│   ├── .storybook/
│   ├── tests/               # vitest helpers
│   ├── package.json
│   ├── pnpm-lock.yaml
│   └── Dockerfile
├── workers/                 # placeholder (Phase 2)
├── ai/                      # placeholder (Phase 8)
├── analyzers/               # placeholder (Phase 2)
├── sdk/                     # placeholder (Phase 10, generated from OpenAPI)
├── deploy/
│   ├── docker-compose.yml
│   ├── docker-compose.override.example.yml
│   └── .env.example
├── docs/
│   ├── architecture.md      # one-pager + system diagram + integration roadmap
│   ├── data-model.md        # stub for Phase 1
│   ├── runbook.md           # local dev runbook
│   ├── api.md               # points to /docs Swagger
│   └── ADRs/                # MADR 3.0
├── .github/
│   └── workflows/{ci.yml, container-scan.yml}
├── .pre-commit-config.yaml
├── .editorconfig
├── .gitignore
├── LICENSE                  # Apache-2.0
├── NOTICE
├── CONTRIBUTING.md          # DCO sign-off required
├── CODE_OF_CONDUCT.md
└── README.md
```

Setiap placeholder folder berisi `README.md` yang menunjuk ke phase yang akan mengisinya — jadi `git clone` tidak menghasilkan folder kosong yang membingungkan kontributor.

### 3.2 Tooling

| Concern | Pilihan | Rasional |
|---|---|---|
| Python dep mgr | **uv** + `pyproject.toml` + `uv.lock` | 10×+ faster dari poetry, single tool install+venv+lock |
| Python lint+format | **Ruff** untuk keduanya | Drop black; satu tool, lebih cepat |
| Python typecheck | **mypy strict** + pydantic plugin | — |
| Python test | **pytest** + pytest-asyncio (strict mode) + pytest-cov + httpx async client + testcontainers | — |
| JS pkg mgr | **pnpm** workspaces (single workspace Phase 0) | De-facto monorepo standard, hard-link store hemat disk |
| JS lint/format | **ESLint** + **Prettier**; tsc strict | — |
| JS test | **Vitest** + Testing Library + happy-dom + MSW + vitest-axe | — |
| Storybook | Storybook 8 + `@storybook/react-vite` + `@storybook/test` (play-functions) | Match Vite engine |
| Pre-commit | `pre-commit` runs ruff, ruff-format, mypy (changed files), prettier, eslint, commitizen | — |
| Commit style | **Conventional Commits**, enforced via `commitlint` PR-title GH Action | — |
| Versioning | `0.1.0-dev` di Phase 0, SemVer setelah Phase 1 | — |

### 3.3 Yang sengaja TIDAK ada di Phase 0

- Worker framework config (Celery/Arq); keputusan di Phase 2.
- AI/LLM router; Phase 8.
- Helm chart; Phase 10.
- SDK generation pipeline; Phase 10.
- Sentry/error reporting; Phase 10.
- Release-please / changelog automation; Phase 10.
- Visual regression (Chromatic); evaluasi Phase 6/10.

---

## 4. Local development stack

### 4.1 `deploy/docker-compose.yml` services

| Service | Image | Port (host) | Tujuan Phase 0 | Healthcheck |
|---|---|---|---|---|
| `postgres` | `pgvector/pgvector:pg16` | 5432 | Primary store, pgvector siap dipakai Phase 8 | `pg_isready -U adhkar` |
| `redis` | `redis:7-alpine` | 6379 | Cache/broker/pubsub; dibangkitkan agar pola stabil & `/readyz` reachable | `redis-cli ping` |
| `minio` | `minio/minio:latest` | 9000 (s3) / 9001 (console) | Object store; init-once container `minio-init` create bucket `adhkar-attachments` | HTTP `/minio/health/ready` |
| `mailhog` | `mailhog/mailhog` | 1025 (smtp) / 8025 (ui) | Capture email dev | TCP 1025 |
| `api` | build `./backend` | 8000 | FastAPI app | HTTP `/healthz` |
| `web` | build `./frontend` (stage `dev`) | 5173 | React shell, hot reload via bind mount | HTTP `/` |

**Init order** (via `depends_on: condition: service_healthy`):
```
postgres ──┐
redis  ────┼─→ api ─→ web
minio  ────┘
mailhog ─────────────┘
```

**Network & volume**: satu bridge `adhkar-net`; named volumes `pgdata`, `redisdata`, `miniodata`. Source code bind-mount untuk hot reload di dev.

**Container naming**: setiap service punya `container_name: adhkar-<service>` eksplisit (`adhkar-postgres`, `adhkar-redis`, `adhkar-minio`, `adhkar-mailhog`, `adhkar-api`, `adhkar-web`). Ini menjamin perintah `docker stop adhkar-redis` di DoD demo (§10.7) bekerja apa pun nama project compose-nya, dan mempermudah log filtering.

### 4.2 Compose profiles

| Profile | Aktifkan | Service tambahan |
|---|---|---|
| (default) | — | services di tabel 4.1 |
| `observability` | `--profile observability` | `jaeger` (jaegertracing/all-in-one, UI :16686) — test OTel exporter |
| `search` | komentar di-file dengan `# Phase 6+` | placeholder OpenSearch siap di-uncomment |

### 4.3 Konfigurasi (`deploy/.env.example`)

```env
# ----- Adhkar core -----
ADHKAR_ENV=dev
ADHKAR_LOG_LEVEL=INFO
ADHKAR_SECRET_KEY=change-me-32-chars-min-xxxxxxxxxxxx

# ----- Database -----
ADHKAR_DB_HOST=postgres
ADHKAR_DB_PORT=5432
ADHKAR_DB_NAME=adhkar
ADHKAR_DB_USER=adhkar
ADHKAR_DB_PASSWORD=adhkar-dev
DATABASE_URL=postgresql+asyncpg://adhkar:adhkar-dev@postgres:5432/adhkar

# ----- Redis -----
REDIS_URL=redis://redis:6379/0

# ----- Object store (S3-compat) -----
ADHKAR_S3_ENDPOINT=http://minio:9000
ADHKAR_S3_ACCESS_KEY=minio-dev
ADHKAR_S3_SECRET_KEY=minio-dev-secret
ADHKAR_S3_BUCKET=adhkar-attachments
ADHKAR_S3_REGION=us-east-1

# ----- Mail (dev) -----
ADHKAR_SMTP_HOST=mailhog
ADHKAR_SMTP_PORT=1025
ADHKAR_SMTP_FROM=adhkar@localhost

# ----- Observability -----
ADHKAR_OTEL_EXPORTER_OTLP_ENDPOINT=
ADHKAR_OTEL_SERVICE_NAME=adhkar-api

# ----- Frontend -----
VITE_API_BASE_URL=http://localhost:8000
```

Backend settings loader: Pydantic `BaseSettings` dengan env prefix `ADHKAR_`, support `DATABASE_URL`/`REDIS_URL` (12-factor). Singleton module-level, injected via FastAPI dependency `Depends(get_settings)`. Tidak ada `os.getenv()` tersebar.

### 4.4 Tidak di Phase 0

- ClamAV / AV sidecar (Phase 3 saat attachment muncul).
- Analyzer sandbox runner (Phase 2).
- `docker-compose.prod.yml` (Phase 10).

---

## 5. Backend skeleton

### 5.1 Application factory

```python
def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings)
    configure_otel(settings)            # no-op kalau OTEL endpoint kosong

    app = FastAPI(
        title="Adhkar API",
        version=__version__,
        openapi_url="/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
        default_response_class=ORJSONResponse,
    )
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(AccessLogMiddleware)
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, ...)
    app.include_router(meta_router)
    register_exception_handlers(app)
    return app
```

Factory, bukan module-level `app = FastAPI()`, supaya test dapat instansiasi dengan settings override.

### 5.2 Layout `backend/adhkar/`

```
adhkar/
├── __init__.py            # __version__
├── main.py                # create_app()
├── api/
│   ├── deps.py            # get_settings, get_db_session (Phase 1+ tambah get_current_user)
│   ├── errors.py          # RFC 7807 handlers
│   └── v1/
│       └── meta.py        # /healthz /readyz /version
├── core/
│   ├── settings.py        # Pydantic BaseSettings (prefix ADHKAR_)
│   ├── logging.py         # structlog JSON
│   ├── otel.py            # OTel SDK bootstrap (FastAPI + SQLAlchemy auto-instrument)
│   └── middleware.py      # RequestIdMiddleware, AccessLogMiddleware
└── db/
    ├── base.py            # DeclarativeBase + naming conventions
    ├── engine.py          # async_engine + AsyncSessionLocal
    └── readiness.py       # check_db, check_redis, check_s3
```

### 5.3 Endpoints Phase 0

| Method | Path | Behavior |
|---|---|---|
| GET | `/healthz` | Liveness. Selalu 200 jika proses hidup. Body `{"status":"ok"}`. Tidak sentuh I/O. |
| GET | `/readyz` | Readiness. Parallel checks DB connect + Redis ping + S3 head-bucket (timeout 1 s each). 200 kalau semua hijau; 503 dengan body `{"checks":{"db":"ok","redis":"down",...}}` kalau ada gagal. |
| GET | `/version` | `{"version":"0.1.0-dev","commit":"<short-sha>","builtAt":"<iso8601>"}`. Diisi via env `ADHKAR_GIT_COMMIT`/`ADHKAR_BUILT_AT` saat docker build (`--build-arg`). |
| GET | `/docs` | Swagger UI. |
| GET | `/redoc` | ReDoc. |
| GET | `/openapi.json` | OpenAPI 3 spec. |

### 5.4 Error handling (RFC 7807) — locked Phase 0

Semua exception path translate ke struktur konsisten:

```json
{
  "type": "https://adhkar.dev/problems/<slug>",
  "title": "Short title",
  "status": 400,
  "detail": "Human-readable",
  "instance": "<request-id>",
  "errors": [...]
}
```

Handler yang di-register Phase 0:
- `RequestValidationError` → 422 problem.
- `HTTPException` → translate ke problem.
- `Exception` → 500 problem (tanpa stacktrace di response, full log di server).

### 5.5 Database & migrations

- SQLAlchemy 2.x async dengan `asyncpg`. Engine lifecycle via FastAPI lifespan.
- Alembic env.py async template (`alembic init -t async`).
- Naming convention SQL ditetapkan di `Base.metadata` (locked Phase 0):
  ```python
  naming_convention = {
      "ix": "ix_%(column_0_label)s",
      "uq": "uq_%(table_name)s_%(column_0_name)s",
      "ck": "ck_%(table_name)s_%(constraint_name)s",
      "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
      "pk": "pk_%(table_name)s",
  }
  ```
- Migrasi awal `0001_init_extensions.py`:
  `CREATE EXTENSION IF NOT EXISTS "uuid-ossp"; CREATE EXTENSION IF NOT EXISTS pgcrypto; CREATE EXTENSION IF NOT EXISTS vector;`
  Tidak ada domain table.
- Entrypoint `api` container menjalankan `alembic upgrade head` sebelum `uvicorn` start. Bisa di-skip via `ADHKAR_SKIP_MIGRATIONS=1`.

### 5.6 Logging

- `structlog` → JSON ke stdout. Setiap line: `request_id`, `service`, `level`, `event`, `ts`.
- Loglevel via `ADHKAR_LOG_LEVEL`.
- Access log middleware: satu line per request dengan `method`, `path`, `status`, `duration_ms`, `request_id`. **Body tidak di-log** (PII).

### 5.7 OpenTelemetry

- Bootstrap di `core/otel.py`. Default disabled.
- Saat enabled: auto-instrument FastAPI + SQLAlchemy + httpx + redis. Exporter OTLP gRPC ke `ADHKAR_OTEL_EXPORTER_OTLP_ENDPOINT`.
- `request_id` ↔ trace link via structlog processor.

### 5.8 Dockerfile (multi-stage)

```
FROM python:3.12-slim AS base
RUN apt-get update && apt-get install -y --no-install-recommends libpq-dev curl && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
# Build-time arg: 'prod' (default) → no dev deps; 'dev' → include dev deps for hot reload container in compose
ARG INSTALL_GROUP=prod
RUN if [ "$INSTALL_GROUP" = "dev" ]; then uv sync --frozen; else uv sync --frozen --no-dev; fi
COPY adhkar ./adhkar
COPY alembic.ini alembic ./
COPY scripts/entrypoint.sh ./scripts/
ARG GIT_COMMIT
ARG BUILT_AT
ENV ADHKAR_GIT_COMMIT=${GIT_COMMIT} ADHKAR_BUILT_AT=${BUILT_AT}
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s CMD curl -fsS http://localhost:8000/healthz || exit 1
ENTRYPOINT ["./scripts/entrypoint.sh"]
CMD ["uvicorn", "adhkar.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
```

### 5.9 Tidak di Phase 0

- Auth (endpoint open semua). Phase 1.
- Audit log table & event/outbox. Phase 1.
- WebSocket. Phase 1.
- Rate limiting. Phase 1.
- Domain models (Organization, User, dst.). Phase 1.
- Repository pattern abstraction. Phase 1 (saat domain pertama).
- `/metrics` Prometheus. Phase 10.

---

## 6. Frontend skeleton

### 6.1 Source layout `frontend/src/`

```
src/
├── main.tsx
├── app/
│   ├── App.tsx              # router + providers
│   ├── AppShell.tsx         # TopBar + LeftNav + <Outlet/>
│   ├── routes.tsx           # TanStack Router
│   └── providers.tsx
├── pages/
│   └── HealthPage.tsx       # /health
├── design-system/
│   ├── tokens.css           # CSS custom properties --adhkar-*
│   ├── tailwind.config.ts   # tokens → theme.extend
│   └── components/
│       ├── Button/
│       ├── Badge/
│       ├── SeverityBadge/   # level: 1|2|3|4
│       └── TLPBadge/        # tlp: white|green|amber|amber-strict|red
├── lib/
│   ├── api.ts               # fetch wrapper; Phase 1+ → generated openapi-typescript client
│   ├── version.ts
│   └── theme.ts             # 'dark'|'light' + localStorage
└── ui/
    ├── TopBar.tsx
    ├── LeftNav.tsx          # placeholder entries with "Coming in Phase N" tooltip
    └── CommandPalette.tsx   # cmdk stub — Phase 0 satu entry "Go to Health"
```

### 6.2 Tooling

| Concern | Pilihan |
|---|---|
| Build | Vite 5 |
| Router | **TanStack Router v1** (type-safe routes) |
| Server state | TanStack Query v5 |
| UI state | Zustand |
| Styling | Tailwind v4 + shadcn/Radix primitives, **M3 tokens via `@theme`** |
| Icons | **Material Symbols Rounded** (variable font, lazy-loaded via `material-symbols/index.css`) |
| Command palette | `cmdk` (styled to M3 Search Bar) |
| Test | Vitest + @testing-library/react + happy-dom + MSW + vitest-axe |
| Storybook | Storybook 8 + `@storybook/react-vite` + `@storybook/test` |

Lihat ADR 0005 untuk rasional Tailwind+Radix-on-M3 vs Material Web Components. Lucide dihapus dari spec versi sebelumnya — semua icon di Phase 0+ pakai Material Symbols Rounded.

### 6.3 Design tokens (`tokens.css`) — M3 vocabulary

Token diekstrak dari Material Theme Builder (source color: `#F59E0B` / amber) dan ditulis sebagai CSS variables. Domain token (severity, TLP) tetap di-pisahkan supaya tidak bisa di-override oleh M3 theming.

```css
:root {
  /* ----- M3 shape system ----- */
  --md-sys-shape-corner-none: 0;
  --md-sys-shape-corner-extra-small: 4px;
  --md-sys-shape-corner-small: 8px;
  --md-sys-shape-corner-medium: 12px;
  --md-sys-shape-corner-large: 16px;
  --md-sys-shape-corner-extra-large: 28px;
  --md-sys-shape-corner-full: 9999px;

  /* ----- M3 type scale (label/body/title/headline) ----- */
  --md-sys-typescale-label-small-size: 11px;
  --md-sys-typescale-label-medium-size: 12px;
  --md-sys-typescale-label-large-size: 14px;
  --md-sys-typescale-body-small-size: 12px;
  --md-sys-typescale-body-medium-size: 14px;
  --md-sys-typescale-body-large-size: 16px;
  --md-sys-typescale-title-small-size: 14px;
  --md-sys-typescale-title-medium-size: 16px;
  --md-sys-typescale-title-large-size: 22px;
  --md-sys-typescale-headline-small-size: 24px;
  --md-sys-typescale-headline-medium-size: 28px;
  --md-sys-typescale-headline-large-size: 32px;

  /* ----- M3 motion easing + duration ----- */
  --md-sys-motion-easing-standard: cubic-bezier(0.2, 0, 0, 1);
  --md-sys-motion-easing-emphasized: cubic-bezier(0.05, 0.7, 0.1, 1);
  --md-sys-motion-duration-short2: 100ms;
  --md-sys-motion-duration-medium2: 250ms;
  --md-sys-motion-duration-long2: 450ms;

  /* ----- typography family ----- */
  --md-sys-typescale-font-plain: "Inter Variable", system-ui, -apple-system, sans-serif;
  --md-sys-typescale-font-brand: "Inter Variable", system-ui, sans-serif;
  --md-sys-typescale-font-mono: "JetBrains Mono Variable", ui-monospace, monospace;

  /* ----- domain (severity 1-4, FIRST.org TLP) — override M3 ----- */
  --adhkar-severity-1: #3b82f6;
  --adhkar-severity-2: #eab308;
  --adhkar-severity-3: #f97316;
  --adhkar-severity-4: #ef4444;
  --adhkar-tlp-white: #ffffff;
  --adhkar-tlp-green: #22c55e;
  --adhkar-tlp-amber: #f59e0b;
  --adhkar-tlp-amber-strict: #d97706;
  --adhkar-tlp-red: #dc2626;
}

/* ----- M3 dark scheme (default) — exported from Material Theme Builder ----- */
:root,
[data-theme="dark"] {
  --md-sys-color-primary: #ffb787;
  --md-sys-color-on-primary: #4f2500;
  --md-sys-color-primary-container: #6f3a05;
  --md-sys-color-on-primary-container: #ffdbc2;

  --md-sys-color-secondary: #e5bf9f;
  --md-sys-color-on-secondary: #422b16;
  --md-sys-color-secondary-container: #5b412a;
  --md-sys-color-on-secondary-container: #ffdbc2;

  --md-sys-color-tertiary: #c3cb88;
  --md-sys-color-on-tertiary: #2c3400;
  --md-sys-color-tertiary-container: #424b0f;
  --md-sys-color-on-tertiary-container: #dfe79e;

  --md-sys-color-error: #ffb4ab;
  --md-sys-color-on-error: #690005;
  --md-sys-color-error-container: #93000a;
  --md-sys-color-on-error-container: #ffdad6;

  --md-sys-color-surface: #181210;
  --md-sys-color-surface-dim: #181210;
  --md-sys-color-surface-bright: #3f3835;
  --md-sys-color-surface-container-lowest: #120c0a;
  --md-sys-color-surface-container-low: #211a17;
  --md-sys-color-surface-container: #251e1b;
  --md-sys-color-surface-container-high: #302925;
  --md-sys-color-surface-container-highest: #3b3330;

  --md-sys-color-on-surface: #f1dfd8;
  --md-sys-color-on-surface-variant: #d8c2b7;
  --md-sys-color-outline: #a08d83;
  --md-sys-color-outline-variant: #52443e;

  --md-sys-color-inverse-surface: #f1dfd8;
  --md-sys-color-inverse-on-surface: #382e2b;
  --md-sys-color-inverse-primary: #8b4f1d;

  --md-sys-color-scrim: #000000;
  --md-sys-color-shadow: #000000;
}

/* ----- M3 light scheme (opt-in via theme toggle) ----- */
[data-theme="light"] {
  --md-sys-color-primary: #8b4f1d;
  --md-sys-color-on-primary: #ffffff;
  --md-sys-color-primary-container: #ffdbc2;
  --md-sys-color-on-primary-container: #2e1500;

  --md-sys-color-secondary: #765a3f;
  --md-sys-color-on-secondary: #ffffff;
  --md-sys-color-secondary-container: #ffdbc2;
  --md-sys-color-on-secondary-container: #2a1808;

  --md-sys-color-tertiary: #5b6325;
  --md-sys-color-on-tertiary: #ffffff;
  --md-sys-color-tertiary-container: #dfe79e;
  --md-sys-color-on-tertiary-container: #181e00;

  --md-sys-color-error: #ba1a1a;
  --md-sys-color-on-error: #ffffff;
  --md-sys-color-error-container: #ffdad6;
  --md-sys-color-on-error-container: #410002;

  --md-sys-color-surface: #fff8f5;
  --md-sys-color-surface-dim: #e3d6cf;
  --md-sys-color-surface-bright: #fff8f5;
  --md-sys-color-surface-container-lowest: #ffffff;
  --md-sys-color-surface-container-low: #fcefe7;
  --md-sys-color-surface-container: #f6e9e2;
  --md-sys-color-surface-container-high: #f1e3dc;
  --md-sys-color-surface-container-highest: #ebddd7;

  --md-sys-color-on-surface: #221a16;
  --md-sys-color-on-surface-variant: #52443e;
  --md-sys-color-outline: #84736c;
  --md-sys-color-outline-variant: #d6c2b8;

  --md-sys-color-inverse-surface: #382e2b;
  --md-sys-color-inverse-on-surface: #fdeee6;
  --md-sys-color-inverse-primary: #ffb787;

  --md-sys-color-scrim: #000000;
  --md-sys-color-shadow: #000000;
}
```

Tailwind `@theme` di `index.css` me-map token M3 → utility class: `bg-surface`, `bg-surface-container`, `bg-surface-container-high`, `text-on-surface`, `text-on-surface-variant`, `border-outline`, `rounded-shape-medium`, `text-title-large`, dst. Theme toggle = ubah `data-theme` di `<html>` + persist di localStorage. Domain token (severity, TLP) di-expose lewat utility yang sama dengan rilis sebelumnya: `text-severity-3`, `bg-tlp-amber`, dll.

Material Symbols Rounded dimuat sekali di `index.css`:
```css
@import "material-symbols/index.css";
.material-symbols-rounded {
  font-variation-settings: "FILL" 0, "wght" 400, "GRAD" 0, "opsz" 24;
}
```

### 6.4 Primitives Phase 0 — M3 mapping

| Komponen | API | M3 anatomy | Stories |
|---|---|---|---|
| `Button` | `variant: 'filled'|'tonal'|'outlined'|'text'|'error'`, `size: 'sm'|'md'|'lg'`, `loading?: boolean`, `icon?: React.ReactNode` | M3 Common Button (5 styles). Filled = primary action, Tonal = secondary, Outlined = alternate prominence, Text = low emphasis, Error = destructive. Optional leading Material Symbol icon. | Default per variant, semua size, loading, disabled, with-icon |
| `Chip` | `variant: 'assist'|'filter'|'input'|'suggestion'`, `selected?: boolean`, `leadingIcon?`, `onRemove?` | M3 Chip family. **Menggantikan `Badge` generic** dari spec versi sebelumnya — chip lebih tepat secara semantik M3. | Per variant + selected state + input chip remove |
| `SeverityBadge` | `level: 1|2|3|4`, `compact?: boolean` | M3 Assist Chip dengan leading dot indicator (color-blind safety: text label tetap wajib) | Each level × {compact, full} |
| `TLPBadge` | `tlp: 'white'|'green'|'amber'|'amber-strict'|'red'` | M3 Outlined Chip variant dengan teks FIRST.org standard (`TLP:RED` dll) | Per TLP value |

`Chip` menggantikan `Badge` dari spec versi sebelumnya. Domain badge (`SeverityBadge`, `TLPBadge`) tetap dipisah dengan alasan yang sama: value finite, a11y (text wajib), reuse Phase 2+. Material Symbols Rounded dipakai sebagai icon di Button (`icon` prop), Chip (`leadingIcon` prop), dan TopAppBar/NavigationDrawer.

Density override (lihat ADR 0005): Button height `sm=28 / md=36 / lg=44` (vs M3 default `32 / 40 / 56`). Chip height `24 px` (vs M3 `32 px`).

### 6.5 AppShell layout — M3 TopAppBar + NavigationDrawer

```
┌────────────────────────────────────────────────────────────┐
│ TopAppBar:  ▲ ADHKAR · breadcrumb     ⌘K · 🌙 · @user      │  48px (M3 default 64; density override)
├────────┬───────────────────────────────────────────────────┤
│ NavDra │                                                   │
│ 224px  │              <Outlet/>                            │
│        │            (surface-container)                    │
│ ◉ Heal │                                                   │
│ ○ Case │  ← disabled, tooltip "Coming Phase 3"             │
│ ○ Aler │                                                   │
│ ○ Task │                                                   │
│ ○ Dash │                                                   │
│ ○ KB   │                                                   │
│ ○ Admin│                                                   │
└────────┴───────────────────────────────────────────────────┘
```

Komponen mengikuti M3 vocabulary:
- **TopAppBar** (komponen `TopAppBar.tsx`) menggantikan istilah `TopBar`. Surface: `surface`. Icon: Material Symbols Rounded.
- **NavigationDrawer** (komponen `NavigationDrawer.tsx`) menggantikan istilah `LeftNav`. Surface: `surface-container-low`. Item aktif: pill background `secondary-container`, text `on-secondary-container` (M3 spec). Item nonaktif: `on-surface-variant` dengan opacity 38% disabled state per M3.
- Main area surface: `surface` (canvas).

Placeholder nav item tetap pakai pola `<NavItem disabled tooltipText="Coming in Phase N"/>`. Struktur sudah punya slot semua phase.

### 6.6 Halaman Health (`/health`)

```
Adhkar status
────────────
API           ✓ Healthy            v0.1.0-dev  (abc1234 · 2026-06-16 10:42 UTC)
Database      ✓ Connected
Redis         ✓ Reachable
Object store  ✓ Bucket "adhkar-attachments" present

[Refresh]
```

Implementasi: TanStack Query polling `/readyz` tiap 10 s. Render checks dari payload. Tes: vitest assert page render dengan MSW mock; satu Playwright E2E ditambahkan Phase 1 (bukan Phase 0).

### 6.7 Dockerfile (multi-stage)

```
FROM node:22-alpine AS deps
RUN corepack enable && corepack prepare pnpm@latest --activate
WORKDIR /app
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

FROM deps AS dev
COPY . .
EXPOSE 5173
CMD ["pnpm", "dev", "--host", "0.0.0.0"]

FROM deps AS build
COPY . .
RUN pnpm build

FROM nginx:alpine AS runtime
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

Compose pakai stage `dev`. Stage `runtime` untuk Phase 10 production image.

### 6.8 Tidak di Phase 0

- Login / auth UI → Phase 1.
- Data grid scaffold (TanStack Table) → Phase 2.
- Filter sidebar layout → Phase 2.
- WebSocket client → Phase 1.
- Adhkar Mind copilot rail → Phase 8.
- i18n → tidak default; tambah saat ada permintaan eksplisit.
- Light theme polish lengkap → Phase 10 (Phase 0 tokens saja).

---

## 7. ADRs (Architecture Decision Records)

Lima ADR ditulis Phase 0 dalam format MADR 3.0. ADR immutable; perubahan = ADR baru dengan `Supersedes:`.

| File | Topik | Decision |
|---|---|---|
| `docs/ADRs/0001-naming-adhkar.md` | Naming & namespace | Adhkar (lihat §2.1) |
| `docs/ADRs/0002-license-apache-core-plus-enterprise.md` | License model | Apache-2.0 core + commercial enterprise plugins (Grafana model). DCO sign-off untuk kontribusi. |
| `docs/ADRs/0003-persistence-postgres-pgvector.md` | Primary store | PostgreSQL 16 + pgvector; repository pattern Phase 1+ supaya backend pluggable. Trade-off vs Cassandra/Elasticsearch/MongoDB ditangkap. |
| `docs/ADRs/0004-search-deferred-opensearch.md` | Search engine | Postgres FTS dulu via `SearchIndex` interface; OpenSearch ditambah saat trigger spesifik tercapai (latency p95 listing > 500 ms @ 500k observables, FTS attachment body, atau permintaan ES API compatibility). |
| `docs/ADRs/0005-ui-design-system-material-design-3.md` | UI design system | Material Design 3, dense + dark default. Tailwind v4 + shadcn/Radix on M3 tokens (Material Theme Builder), Material Symbols Rounded, M3 button + chip variants. Density overrides + domain color overrides (severity, TLP) didokumentasikan. |

ADR berikutnya akan ditulis di phase masing-masing (auth lib di Phase 1; worker framework di Phase 2; embedding model di Phase 8; HA topology di Phase 10).

---

## 8. Testing strategy

### 8.1 Piramida (pola yang dipasang Phase 0, diisi terus per phase)

```
E2E (Playwright)             Phase 1+ (login)      ~30s/test
Integration (real deps)      Phase 0: 1            1-3s/test
Component (Vitest+RTL+SB)    Phase 0: 4 primitives ~50ms/test
Unit (pytest, vitest)        Phase 0: ~10          <10ms/test
```

### 8.2 Backend

**Layout:**
```
tests/
├── conftest.py
├── factories/                 # Polyfactory (Phase 1+)
├── unit/
│   ├── test_settings.py
│   ├── test_logging.py
│   ├── test_errors.py
│   └── test_middleware.py
└── integration/
    ├── test_health.py
    └── test_readyz.py         # testcontainers
```

**Konvensi locked Phase 0:**
- Unit = no I/O.
- Integration = real deps via testcontainers; mock cuma external HTTP (`respx`).
- `pytest-asyncio` strict mode.
- Polyfactory untuk data (Phase 1+).
- No `time.sleep`; pakai `freezegun` atau injectable clock.
- `pytest-randomly` aktif.
- One test, one assertion (default).
- Test name = behavior, bukan nomor urut.

**Cakupan Phase 0 (~10 tes):**
1. `Settings` parse `ADHKAR_*` env vars dengan default benar.
2. `Settings` reject `SECRET_KEY` < 32 chars.
3. JSON logger output punya `request_id`, `event`, `level`, `ts`.
4. RFC 7807 handler `RequestValidationError` → 422 struktur benar.
5. RFC 7807 `HTTPException` → struktur benar, no stacktrace.
6. RFC 7807 `Exception` → 500 + log lengkap.
7. RequestId middleware accept `X-Request-Id` incoming dan propagate.
8. RequestId middleware generate UUID kalau header absent.
9. `/healthz` → 200 tanpa I/O.
10. `/readyz` → 200 dengan semua checks "ok" (testcontainers up); 503 dengan body checks ter-flagged saat Redis di-pause.

### 8.3 Frontend

**Layout:**
```
src/
├── design-system/components/Button/
│   ├── Button.tsx
│   ├── Button.test.tsx           # behavior
│   └── Button.stories.tsx        # play-function
└── pages/
    └── HealthPage.test.tsx       # mock fetch dengan MSW

tests/
└── e2e/                           # Phase 1+ Playwright
```

**Konvensi locked Phase 0:**
- Storybook = source of truth untuk visual states.
- `@storybook/test` play-functions auto-jalan via `test-storybook` di CI.
- Visual regression opt-in (Chromatic/Loki); **tidak** Phase 0.
- MSW di setup; konvensi mock API.
- A11y: vitest-axe; tiap primitive punya 1 axe test (zero violation rule).
- No snapshot tests.

**Cakupan Phase 0 (~10 tes komponen + 2 page):**
- Per primitive (Button, Badge, SeverityBadge, TLPBadge): 1 behavior + 1 axe + 1 play-function.
- HealthPage: 1 healthy + 1 with one check down.

E2E Phase 0 = 0 (didokumentasikan di runbook agar tidak terlihat sebagai kelalaian).

### 8.4 Coverage policy

| Phase | Backend min | Frontend min |
|---|---|---|
| 0 | 70% per-file | 60% per-file |
| 1 | 75% | 65% |
| 2–9 | +1–2%/phase, ceiling 85% | id. |
| 10 | freeze + audit | id. |

Per-file via `--cov-fail-under-per-file` mencegah test theatre.

### 8.5 Security testing

- **Bandit** di CI (warn-only Phase 0, fail Phase 10).
- **Semgrep** rule pack `p/owasp-top-ten` + `p/python` + `p/typescript`; fail on ERROR.
- **`pip-audit` / `pnpm audit`** weekly via `container-scan.yml`.
- **OWASP ZAP baseline** Phase 1+ (saat ada login endpoint).

### 8.6 Performance & smoke

- `docker compose up` boot-to-healthy timing di-track di CI. Phase 0 target **< 60 s** di ubuntu-latest. Naik jadi regression budget Phase 10.
- Load test (k6) Phase 10.

### 8.7 Tidak di Phase 0

- Mutation testing.
- Property-based (Hypothesis) — Phase 1.
- Contract testing (Pact).
- Visual regression.
- Chaos engineering.

---

## 9. CI pipeline (GitHub Actions)

### 9.1 Workflow files

```
.github/workflows/
├── ci.yml                  # pull_request + push to main
└── container-scan.yml      # cron weekly + push to main
```

Plus `pull_request_template.md` dan CODEOWNERS (`docs/ADRs/* @<owner>`).

### 9.2 `ci.yml` jobs

| Job | Depends on | Trigger condition | Steps |
|---|---|---|---|
| `changes` | — | always | paths-filter detect backend/frontend/docs/deploy changes |
| `backend-quality` | `changes` | backend changed | uv sync; ruff check; ruff format --check; mypy adhkar; pytest --cov --cov-fail-under=70 (per-file) |
| `frontend-quality` | `changes` | frontend changed | pnpm install; pnpm lint; pnpm format:check; pnpm typecheck; pnpm test --run; pnpm build; pnpm storybook:build |
| `integration` | backend+frontend quality | always (pada PR) | service containers postgres+redis+minio; alembic upgrade head; pytest tests/integration |
| `build-images` | integration | push to main / release tag | docker buildx; push backend+frontend ke ghcr.io dengan tag `sha-<short>` + `:main`; SBOM SPDX via anchore/sbom-action; cosign keyless OIDC sign |
| `commitlint` | — | PR | wagoid/commitlint-github-action (warn-only Phase 0, blocking Phase 1) |

Concurrency group per-branch + `cancel-in-progress: true`.

### 9.3 `container-scan.yml`

- Trigger: `schedule: '0 6 * * 1'` + push to main.
- Jobs: `trivy-fs` (manifest scan), `trivy-image` (latest images), `upload-sarif` (Code Scanning tab).
- Severity gate: CRITICAL = fail; HIGH = warn Phase 0, fail Phase 10.

### 9.4 Branch protection (dokumentasi runbook; di-set manual di GitHub)

- `main` protected; required checks: backend-quality, frontend-quality, integration.
- Linear history (rebase only).
- Required review: 1.
- Conventional Commits via commitlint job: warn Phase 0, blocking Phase 1.

### 9.5 Pre-commit mirror

`.pre-commit-config.yaml`: ruff, ruff-format, mypy (changed files), prettier, eslint --fix, commitizen check.

### 9.6 Tidak di Phase 0

- Release-please / changelog generator.
- Performance benchmark.
- Mutation testing.
- Helm chart lint.
- Multi-Python-version matrix.
- macOS/Windows runner.
- Pin Actions ke SHA (Phase 10, Renovate-managed).

---

## 10. Definition of Done

Phase 0 disebut **Done** jika dan hanya jika semua butir berikut hijau.

### 10.1 Repo & dokumen
- [ ] Repo `adhkar-ir` di GitHub, public, Apache-2.0 + NOTICE + CONTRIBUTING (DCO) + CODE_OF_CONDUCT + PR template + CODEOWNERS.
- [ ] Layout direktori sesuai §3.1; tiap placeholder folder berisi `README.md` mengarah ke phase pengisinya.
- [ ] Lima ADR di `docs/ADRs/` (naming, license, persistence, search-deferred, UI design system M3) — status `Accepted`.
- [ ] `docs/architecture.md` satu halaman + system diagram (mermaid) + seksi **Integration roadmap** (§11).
- [ ] `docs/runbook.md`: prerequisites, `docker compose up` sekali jalan, cara reset (`docker compose down -v`), cara lihat Swagger/Storybook, troubleshooting 5 error paling umum.
- [ ] `README.md` root: tagline 1 kalimat, "Quick start" 3-langkah, link ke runbook, badge CI.

### 10.2 Local stack
- [ ] `cd deploy && cp .env.example .env && docker compose up -d` → semua service `healthy` dalam < 60 detik di mesin developer.
- [ ] `docker compose down -v && docker compose up -d` kembali ke fresh tanpa intervensi (auto-create bucket, auto-`alembic upgrade head`).

### 10.3 Backend
- [ ] `GET /healthz` → `200 {"status":"ok"}`.
- [ ] `GET /readyz` → `200` body `{"checks":{"db":"ok","redis":"ok","s3":"ok"}}`; matikan satu service → `503` dengan status per-check akurat.
- [ ] `GET /version` → struktur lengkap dengan `commit` + `builtAt`.
- [ ] `GET /docs` (Swagger) load; OpenAPI spec di `/openapi.json` lulus `openapi-spec-validator`.
- [ ] Semua endpoint error path RFC 7807 problem+json; unit test ada per handler.
- [ ] Alembic `0001_init_extensions` ada di `versions/`; `upgrade head` idempoten; `downgrade base` clean.
- [ ] Structured JSON log dengan `request_id` tiap request.
- [ ] OTel bootstrap callable; default disabled; aktif via `--profile observability` + Jaeger menampilkan trace.

### 10.4 Frontend
- [ ] `http://localhost:5173/` load dark theme, no console errors, no axe baseline violation.
- [ ] AppShell render; nav disabled items punya tooltip "Coming in Phase N".
- [ ] `/health` menampilkan status API/DB/Redis/S3 real-time saat container di-stop/start.
- [ ] Theme toggle pindah light theme + persist setelah reload.
- [ ] ⌘K membuka command palette stub dengan minimal "Go to Health".
- [ ] `pnpm storybook` membuka Storybook dengan empat primitive (Button 5 variants, Chip 4 variants, SeverityBadge, TLPBadge); Material Symbols Rounded ter-load tanpa FOUT; tiap primitive punya default + variant + play-function.

### 10.5 Quality gates (CI green di PR pertama dan `main`)
- [ ] `backend-quality`: ruff check, ruff format --check, mypy strict, pytest dengan coverage ≥ 70% per-file.
- [ ] `frontend-quality`: eslint, prettier --check, tsc --noEmit, vitest coverage ≥ 60% per-file, `pnpm build`, `pnpm storybook:build`.
- [ ] `integration`: services postgres+redis+minio; alembic upgrade head; `test_readyz` hijau.
- [ ] `build-images` (push main): images ter-publish ke `ghcr.io/<org>/adhkar-{api,web}:sha-<short>` + `:main`; SBOM SPDX terlampir; cosign signature ada.
- [ ] `container-scan` weekly: terjadwal; CRITICAL = fail; HIGH = warn.

### 10.6 Repo hygiene
- [ ] `pre-commit install` bekerja; hooks menangkap kesalahan lokal.
- [ ] Branch protection di `main` aktif: required checks (3), required review 1, linear history.
- [ ] Conventional Commits commitlint job hijau pada PR uji-coba.

### 10.7 Sanity demo (screencast 90 detik untuk arsip)
- [ ] `git clone … && cd … && docker compose up -d && open http://localhost:5173`.
- [ ] Health page hijau → `docker stop adhkar-redis` → Redis menunjukkan down → `docker start adhkar-redis` → kembali hijau.
- [ ] Tunjukkan Swagger `:8000/docs`, Storybook `:6006`, MailHog `:8025`, MinIO console `:9001`.

Jika satu butir tidak hijau → Phase 0 belum done; tidak boleh mulai Phase 1.

---

## 11. Integration roadmap (di-document ke `docs/architecture.md`)

Adhkar dirancang sebagai platform integrasi, bukan re-implementasi EDR/SIEM. Integrasi pihak ketiga mendarat di tiga lapisan, masing-masing pada phase yang berbeda.

| Lapisan | Mendarat | Vendor/protokol yang ditangani |
|---|---|---|
| **Intake** (alert masuk) | Phase 4 framework, paket vendor Phase 7 | SIEM (Splunk, Elastic, Sentinel, QRadar) via webhook; EDR (CrowdStrike Falcon Streaming, SentinelOne Activities, Trellix HX, Symantec EDR) via feeder; MISP via dedicated connector; email-to-alert (IMAP / MS Graph) |
| **Enrichment & response** (analyzer + responder) | Phase 2 engine, paket vendor Phase 7 | EDR query/containment (Falcon RTR, S1 remote shell, Trellix isolation, Symantec quarantine); firewall blocks (Palo Alto, Fortinet, Cisco); ticketing (Jira, ServiceNow); IM (Slack, Teams, Mattermost); threat intel (VirusTotal, AbuseIPDB, Shodan, URLScan, Hybrid Analysis, MISP lookup); enrichment generik (GeoIP, DNS/WHOIS, hash reputation) |
| **Orchestration** (rangkaian aksi otomatis) | Phase 5 automation engine | FilteredEvent triggers → notifier / RunResponder / Function — memungkinkan playbook seperti "severity≥3 + observable hash dikenal di TI → auto-isolate host via Falcon RTR + buat Jira ticket" sebagai konfigurasi, bukan kode |

**Akses cepat sebelum first-party paket matang**: Phase 7 ship juga **Cortex compatibility shim** sehingga analyzer/responder komunitas yang sudah ada untuk vendor di atas (di repo `TheHive-Project/Cortex-Analyzers`) bisa langsung dipakai tanpa rewrite.

**Komitmen non-fork**: stable plugin SDK dari Phase 2 menjamin pelanggan/komunitas dapat menulis integrasi vendor sendiri (termasuk EDR/EPP yang tidak tercantum — Microsoft Defender for Endpoint, Cybereason, Cortex XDR, dsb.) tanpa mem-fork core. Itu memenuhi janji license ADR 0002.

**Decomposition Phase 7**: saat brainstorm Phase 7, scope-nya akan dipecah menjadi:
- **7a**: auth providers (AD/LDAP/OAuth2/OIDC/SAML), SMTP, MISP, email intake, Cortex shim.
- **7b**: first-party EDR/SIEM/firewall paket vendor lengkap, prioritas berdasar adopsi (typically CrowdStrike + SentinelOne dahulu).

---

## 12. Handoff: peek Phase 1

Phase 1 = **Identity, Tenancy, RBAC, Audit, Event/Outbox, Live-Feed plumbing**. Foundation domain. Setelah Phase 1, setiap endpoint di phase berikutnya berdiri di atas authz + audit + event yang sudah jadi.

**Scope tentatif** (akan di-brainstorm sebagai spec terpisah):
1. Entitas: `Organization`, `User`, `UserOrgMembership`, `Profile`, `Permission`, `ApiKey`, `Session`, `MfaSecret`, `OrgSharing`, `AuditLog`, `OutboxEvent`.
2. Local auth: argon2id, login/logout dengan JWT access+refresh, revocation via Redis denylist, password reset via MailHog, password policy.
3. MFA: TOTP only (RFC 6238 + QR setup); WebAuthn ditunda Phase 7/10.
4. API keys: per-user, scoped, hashed-at-rest, prefix `aeg_` (leak-scanner friendly).
5. RBAC engine: Profile = named permission set; resolver `require_permission("manageCase")` sebagai dependency; cache per session di Redis, invalidated on update.
6. Multi-tenancy enforcement: `OrgScope` repository wrapper menambahkan `WHERE organization_id = :current_org` automatically. Tidak optional.
7. Audit log: append-only table, satu row per mutation (actor/action/entity/diff/request_id/ip). View via `GET /v1/audit?...`. Permission `viewAudit` terpisah.
8. Event/Outbox: tabel `outbox_events` di-tulis transactional dengan mutation; worker (minimal asyncio Phase 1; full Celery/Arq Phase 2) publish ke Redis pub/sub.
9. Live-feed WebSocket: `ws /v1/live`, authenticated, multiplex per-org channel. Frontend `useLiveFeed()`. Phase 1 cuma event "user created/logged in" — plumbing lengkap.
10. Frontend: login + MFA setup + reset password; user menu (logout, switch org); Admin > Users; Admin > Organizations; Admin > Profiles (RBAC editor); Audit log viewer; presence indicator.

**Penjelasan scope ke depan**: brainstorm Phase 4 (intake) akan men-design pola Feeder + Webhook generik yang dipakai EDR/SIEM. Brainstorm Phase 7 dipecah jadi 7a/7b seperti dijelaskan §11. Decomposition ini bukan keputusan sekarang — hanya pin di-dokumen agar tidak hilang.

Phase 1 ukuran ~3–4× Phase 0. Rekomendasi: brainstorm Phase 1 akan mempertimbangkan dekomposisi 1a (Org/User/Profile/Auth/MFA/ApiKey + Admin UI dasar) dan 1b (Audit + Event/Outbox + Live-feed + presence).

---

## 13. Out of scope (eksplisit)

Hal-hal berikut **bukan** Phase 0. Tertulis di sini agar tidak ada ambiguitas tentang apa yang harus di-ship.

- Domain entities apa pun (Organization, User, Case, Alert, Observable, Task) — Phase 1+.
- Authentication / authorization — Phase 1.
- WebSocket plumbing — Phase 1.
- Analyzer / responder engine dan plugin SDK — Phase 2.
- Helm chart, production compose, HA topology — Phase 10.
- SDK generation (`adhkar-py`, `adhkar-go`) — Phase 10.
- License enforcement module — tidak akan ditambahkan; license enforcement diserahkan ke plugin presence (lihat ADR 0002).
- Email intake (IMAP/MS Graph) — Phase 7a.
- MISP connector — Phase 7a.
- OpenSearch — ditunda; lihat ADR 0004 untuk trigger re-evaluasi.
- i18n — tidak default; tambah kalau ada permintaan eksplisit.
- Visual regression (Chromatic/Loki) — evaluasi Phase 6/10.
- `/metrics` Prometheus endpoint — Phase 10.

---

## 14. Risk register & mitigasi (Phase 0)

| Risiko | Likelihood | Impact | Mitigasi |
|---|---|---|---|
| Compose boot > 60 s di runner CI (test gagal) | Medium | Medium | Pin image digest; tune Postgres `shared_buffers` minimal; healthcheck interval cepat |
| Vite v5 + Tailwind v4 + Storybook 8 compatibility friction | Medium | Low | Lock semua versi di `pnpm-lock.yaml`; storybook-build di CI menangkap regresi |
| `uv` ekosistem masih muda (v0.x) → breaking changes | Low | Low | Pin `uv` version di Dockerfile dan CI; fallback `pip-tools` dokumentasikan |
| pgvector extension absen di image yang salah | Low | High | Image `pgvector/pgvector:pg16` dipakai langsung; migrasi `0001` melakukan `CREATE EXTENSION vector` sebagai assertion |
| cosign keyless butuh GitHub OIDC permissions yang benar | Medium | Low | `permissions: id-token: write` di workflow `build-images`; runbook menjelaskan setup |
| Self-hoster bingung dengan `--profile observability` | Low | Low | Runbook dokumentasi eksplisit; default tanpa profile = no Jaeger |

---

## 14a. Placeholder convention

Spec ini memakai dua placeholder yang harus diganti saat repo dibuat. Implementer tidak boleh meninggalkan keduanya sebagai literal `<...>`:

| Placeholder | Diganti dengan | Muncul di |
|---|---|---|
| `<org>` | GitHub organization atau username pemilik repo | `ghcr.io/<org>/adhkar-*` (§3.1, §9.2, §10.5), `gh:<org>/adhkar-ir` (README badge) |
| `<owner>` | GitHub handle yang berperan CODEOWNER untuk ADR | `CODEOWNERS` entry (§9.1) |

Diisi saat task "init repo" di implementation plan, bukan ditinggal untuk fase berikutnya.

---

## 15. References

- Brief produk asli (mission, scope §1–§13).
- TheHive 5 documentation (StrangeBee) — baseline functional parity target.
- MADR 3.0 template — ADR format.
- FIRST.org TLP 2.0 — TLP color taxonomy.
- MITRE ATT&CK — TTP catalog (Phase 3+).
- OWASP ASVS Level 2 — security baseline.
- Conventional Commits 1.0 — commit message format.
- 12-Factor App — config patterns.

---

End of spec. Setelah approve, lanjut ke `superpowers:writing-plans` untuk implementation plan Phase 0.
