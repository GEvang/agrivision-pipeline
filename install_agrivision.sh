#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

PYTHON_BIN="$PROJECT_ROOT/venv/bin/python"

echo "=============================================="
echo "        AgriVision ADS Installer"
echo "=============================================="
echo "[System] Project root: $PROJECT_ROOT"

echo "[System] Updating apt..."
sudo apt update

echo "[System] Installing base system packages..."
sudo apt install -y \
  git \
  python3 python3-venv python3-pip \
  gdal-bin \
  ca-certificates curl gnupg

echo "[Docker] Ensuring Docker Engine is installed..."
if ! command -v docker >/dev/null 2>&1; then
  sudo apt remove -y docker.io docker-doc docker-compose podman-docker containerd runc || true
  sudo install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
    sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  sudo chmod a+r /etc/apt/keyrings/docker.gpg
  echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
    https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | \
    sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
  sudo apt update
  sudo apt install -y \
    docker-ce docker-ce-cli containerd.io \
    docker-buildx-plugin docker-compose-plugin
fi

sudo systemctl enable docker
sudo systemctl start docker

echo "[Python] Creating virtual environment..."
if [ ! -d "venv" ]; then
  python3 -m venv venv
fi

# shellcheck disable=SC1091
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
deactivate

echo "[Folders] Creating AgriVision folder structure..."
mkdir -p data/images_full/rgb data/images_full/mapir
mkdir -p data/images_resized/rgb data/images_resized/mapir
mkdir -p data/odm_project_rgb data/odm_project_mapir
mkdir -p output/ndvi output/runs output/weather output/irrigation

echo "[Docker] Pulling ODM image..."
sudo docker pull opendronemap/odm:latest

echo "[Services] Preparing OpenAgri WeatherService and IrrigationManagement repos..."
"$PYTHON_BIN" - <<'PY'
from pathlib import Path

from agrivision.services.irrigation.runtime import ensure_repo_and_env as ensure_irrigation_repo_and_env
from agrivision.services.weather.client import _ensure_weather_repo_and_env

project_root = Path.cwd()
print(f"[Services] Working from {project_root}")
weather_repo_dir, weather_compose = _ensure_weather_repo_and_env()
print(f"[Services] Weather repo ready: {weather_repo_dir}")
print(f"[Services] Weather compose file: {weather_compose}")
irr_repo_dir, irr_compose = ensure_irrigation_repo_and_env()
print(f"[Services] Irrigation repo ready: {irr_repo_dir}")
print(f"[Services] Irrigation compose file: {irr_compose}")
PY

echo "[Services] Starting WeatherService and IrrigationManagement..."
"$PYTHON_BIN" - <<'PY'
from agrivision.services.irrigation.runtime import start_service_if_needed
from agrivision.services.weather.client import _get_weather_settings, _start_weather_service_if_needed

weather_base_url = _get_weather_settings()["base_url"]
_start_weather_service_if_needed(weather_base_url)
start_service_if_needed(verbose=True)
print("[Services] External services are prepared and startable.")
PY

echo "[Done] Installation complete."
echo "Activate the venv and run: python run.py"
