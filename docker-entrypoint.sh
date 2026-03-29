#!/usr/bin/env bash
set -euo pipefail

cd /workspace
mkdir -p /workspace/output /workspace/data

if [ -f "/workspace/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  source /workspace/.env
  set +a
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "[Docker entrypoint] WARNING: docker CLI not available inside container." >&2
fi

if [ ! -S /var/run/docker.sock ]; then
  echo "[Docker entrypoint] WARNING: /var/run/docker.sock not mounted. ODM stages will fail." >&2
fi

exec "$@"
