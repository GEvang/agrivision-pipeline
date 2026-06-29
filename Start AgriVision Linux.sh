#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is not installed or not on PATH."
  echo "Install Docker, then run this launcher again."
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "Docker is installed but not running."
  echo "Start Docker, then run this launcher again."
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "docker compose is not available."
  echo "Install the Docker Compose plugin, then run this launcher again."
  exit 1
fi

echo "Starting AgriVision dashboard..."
docker compose up --build -d

echo "Starting host service helper..."
chmod +x "$PWD/scripts/service-helper-posix.sh"
nohup "$PWD/scripts/service-helper-posix.sh" >/dev/null 2>&1 &

echo "AgriVision is available at http://127.0.0.1:8008"
if command -v xdg-open >/dev/null 2>&1; then
  xdg-open "http://127.0.0.1:8008" >/dev/null 2>&1 || true
fi
