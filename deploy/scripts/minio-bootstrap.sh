#!/usr/bin/env sh
# Bootstraps the MinIO bucket on first run. Idempotent.
set -eu

ENDPOINT="${MINIO_ENDPOINT:-http://minio:9000}"
ACCESS_KEY="${MINIO_ROOT_USER}"
SECRET_KEY="${MINIO_ROOT_PASSWORD}"
BUCKET="${BUCKET_NAME:-adhkar-attachments}"

echo "[minio-init] waiting for minio at $ENDPOINT"
until /usr/bin/mc alias set local "$ENDPOINT" "$ACCESS_KEY" "$SECRET_KEY" >/dev/null 2>&1; do
  sleep 1
done

if /usr/bin/mc ls "local/$BUCKET" >/dev/null 2>&1; then
  echo "[minio-init] bucket $BUCKET already exists"
else
  /usr/bin/mc mb "local/$BUCKET"
  echo "[minio-init] bucket $BUCKET created"
fi
