#!/usr/bin/env sh
set -eu

# Run migrations unless explicitly skipped (e.g., from compose for one-shot debugging).
if [ "${ADHKAR_SKIP_MIGRATIONS:-0}" = "0" ]; then
  echo "[entrypoint] running alembic upgrade head"
  uv run alembic upgrade head
fi

echo "[entrypoint] starting uvicorn"
exec "$@"
