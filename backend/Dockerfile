# syntax=docker/dockerfile:1.7

FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

RUN apt-get update \
 && apt-get install -y --no-install-recommends curl libpq-dev xmlsec1 libxmlsec1-dev \
 && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.4.30 /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./

ARG INSTALL_GROUP=prod
RUN if [ "$INSTALL_GROUP" = "dev" ]; then \
      uv sync --frozen; \
    else \
      uv sync --frozen --no-dev; \
    fi

COPY adhkar ./adhkar
COPY alembic.ini ./
COPY alembic ./alembic
COPY scripts ./scripts
RUN chmod +x ./scripts/entrypoint.sh

ARG GIT_COMMIT=unknown
ARG BUILT_AT=unknown
ENV ADHKAR_GIT_COMMIT=${GIT_COMMIT} \
    ADHKAR_BUILT_AT=${BUILT_AT}

EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
  CMD curl -fsS http://localhost:8000/healthz || exit 1

ENTRYPOINT ["./scripts/entrypoint.sh"]
CMD ["uvicorn", "adhkar.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
