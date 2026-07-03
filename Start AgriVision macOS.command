#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker Desktop is not installed or docker is not on PATH."
  echo "Install Docker Desktop, start it, then run this launcher again."
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "Docker Desktop is installed but not running."
  echo "Start Docker Desktop, then run this launcher again."
  exit 1
fi

echo "Starting AgriVision dashboard..."
docker compose up --build -d

echo "Starting host service helper..."
chmod +x "$PWD/scripts/service-helper-posix.sh"
nohup "$PWD/scripts/service-helper-posix.sh" >/dev/null 2>&1 &

echo "AgriVision is available at http://127.0.0.1:8008"
open "http://127.0.0.1:8008"
