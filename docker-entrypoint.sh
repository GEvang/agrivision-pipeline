#!/usr/bin/env bash
set -euo pipefail

cd /app
mkdir -p /app/output /app/data /app/runtime /app/runtime/runs /app/runtime/exports

if [ -f "/app/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  source /app/.env
  set +a
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "[Docker entrypoint] WARNING: docker CLI not available inside container." >&2
fi

if [ ! -S /var/run/docker.sock ]; then
  echo "[Docker entrypoint] INFO: /var/run/docker.sock is not mounted. Dashboard startup is fine; ODM and advanced service controls remain unavailable." >&2
fi

exec "$@"
