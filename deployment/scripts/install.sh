#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

export PROJECT_ROOT
cd "$PROJECT_ROOT"

echo "=============================================="
echo "        AgriVision ADS Installer"
echo "=============================================="
echo "[System] Project root: $PROJECT_ROOT"

echo "[System] Updating apt..."
sudo apt update

echo "[System] Installing base system packages..."
sudo apt install -y \
  python3 python3-venv python3-pip \
  gdal-bin git \
  ca-certificates curl gnupg lsb-release

if command -v docker >/dev/null 2>&1; then
  echo "[Docker] Docker already installed: $(docker --version)"
else
  echo "[Docker] Installing Docker Engine..."
  sudo apt remove -y docker.io docker-doc docker-compose podman-docker containerd runc || true
  sudo install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  sudo chmod a+r /etc/apt/keyrings/docker.gpg
  echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" |
    sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
  sudo apt update
  sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi

sudo systemctl enable docker
sudo systemctl start docker

venv_created=0
if [ ! -d "$PROJECT_ROOT/venv" ]; then
  python3 -m venv "$PROJECT_ROOT/venv"
  venv_created=1
fi

# shellcheck disable=SC1091
source "$PROJECT_ROOT/venv/bin/activate"
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r "$PROJECT_ROOT/requirements.txt"
python -m pip install -e "$PROJECT_ROOT[dev]"

mkdir -p \
  "$PROJECT_ROOT/data/images_full/rgb" \
  "$PROJECT_ROOT/data/images_full/mapir" \
  "$PROJECT_ROOT/data/images_resized/rgb" \
  "$PROJECT_ROOT/data/images_resized/mapir" \
  "$PROJECT_ROOT/data/odm_project_rgb" \
  "$PROJECT_ROOT/data/odm_project_mapir" \
  "$PROJECT_ROOT/output/ndvi" \
  "$PROJECT_ROOT/output/runs" \
  "$PROJECT_ROOT/output/irrigation" \
  "$PROJECT_ROOT/output/weather"

sudo docker pull opendronemap/odm:latest || true

if [ -f "$PROJECT_ROOT/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  source "$PROJECT_ROOT/.env"
  set +a
fi

python - <<'INNERPY'
from agrivision.services.irrigation.runtime import ensure_repo_and_env, start_service_if_needed
from agrivision.services.weather.client import ensure_weather_repo_and_env, _ensure_weather_service_available

print("[Weather] Reconciling repo, env, and service runtime...")
try:
    ensure_weather_repo_and_env()
    _ensure_weather_service_available()
    print("[Weather] Service is reachable and config is reconciled.")
except Exception as exc:
    print(f"[Weather] Service bootstrap incomplete: {exc}")

print("[Irrigation] Reconciling repo, env, and service runtime...")
try:
    ensure_repo_and_env()
    start_service_if_needed()
    print("[Irrigation] Service is reachable and config is reconciled.")
except Exception as exc:
    print(f"[Irrigation] Service bootstrap incomplete: {exc}")
INNERPY

deactivate

echo "[Done] Installation complete."
if [ "$venv_created" -eq 1 ]; then
  echo "[Done] A new virtual environment was created. Activate it with: source venv/bin/activate"
fi
