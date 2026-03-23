#!/usr/bin/env bash
set -euo pipefail

echo "=============================================="
echo "        AgriVision ADS Installer"
echo "=============================================="

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

echo "[System] Project root: $PROJECT_ROOT"
echo "[System] Updating apt..."
sudo apt update

echo "[System] Installing base system packages..."
sudo apt install -y \
  python3 python3-venv python3-pip \
  gdal-bin git \
  ca-certificates curl gnupg

if command -v docker >/dev/null 2>&1; then
  echo "[Docker] Docker already installed: $(docker --version)"
else
  echo "[Docker] Installing Docker Engine..."
  sudo apt remove -y docker.io docker-doc docker-compose podman-docker containerd runc || true
  sudo install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  sudo chmod a+r /etc/apt/keyrings/docker.gpg
  echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
    https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | \
    sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
  sudo apt update
  sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi

sudo systemctl enable docker
sudo systemctl start docker

if [ ! -d "venv" ]; then
  python3 -m venv venv
fi

# shellcheck disable=SC1091
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install pytest ruff

mkdir -p data/images_full/rgb data/images_full/mapir
mkdir -p data/images_resized/rgb data/images_resized/mapir
mkdir -p data/odm_project_rgb data/odm_project_mapir
mkdir -p output/ndvi output/runs output/irrigation output/weather

sudo docker pull opendronemap/odm:latest || true

if [ -f ".env" ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

python - <<'PY'
from agrivision.services.irrigation.runtime import ensure_repo_and_env, start_service_if_needed
from agrivision.services.weather.client import (
    _ensure_weather_service_available,
    ensure_weather_repo_and_env,
)

print("[Weather] Preparing repo, env, and service...")
ensure_weather_repo_and_env()
try:
    _ensure_weather_service_available()
    print("[Weather] Service is reachable.")
except Exception as exc:
    print(f"[Weather] Service bootstrap incomplete: {exc}")

print("[Irrigation] Preparing repo, env, and service...")
ensure_repo_and_env()
try:
    start_service_if_needed()
    print("[Irrigation] Service is reachable.")
except Exception as exc:
    print(f"[Irrigation] Service bootstrap incomplete: {exc}")
PY

deactivate

echo "[Done] Installation complete."
