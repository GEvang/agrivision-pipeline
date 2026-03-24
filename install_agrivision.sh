#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"
VENV_DIR="$PROJECT_ROOT/.venv"

cd "$PROJECT_ROOT"

echo "=============================================="
echo "     AgriVision Pipeline Installer"
echo "=============================================="
echo "[System] Project root: $PROJECT_ROOT"

echo "[System] Updating apt package index..."
sudo apt update

echo "[System] Installing required system packages..."
sudo apt install -y   python3   python3-venv   python3-pip   gdal-bin   git   ca-certificates   curl   gnupg   lsb-release

if command -v docker >/dev/null 2>&1; then
  echo "[Docker] Docker already installed: $(docker --version)"
else
  echo "[Docker] Installing Docker Engine..."
  sudo apt remove -y docker.io docker-doc docker-compose podman-docker containerd runc || true
  sudo install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  sudo chmod a+r /etc/apt/keyrings/docker.gpg
  echo     "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" |
    sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
  sudo apt update
  sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi

sudo systemctl enable docker
sudo systemctl start docker

if [ ! -d "$VENV_DIR" ]; then
  echo "[Python] Creating virtual environment at $VENV_DIR"
  python3 -m venv "$VENV_DIR"
else
  echo "[Python] Reusing existing virtual environment at $VENV_DIR"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r "$PROJECT_ROOT/requirements.txt"
python -m pip install -e "$PROJECT_ROOT[dev]"

deactivate

mkdir -p   "$PROJECT_ROOT/data/images_full/rgb"   "$PROJECT_ROOT/data/images_full/mapir"   "$PROJECT_ROOT/data/images_resized/rgb"   "$PROJECT_ROOT/data/images_resized/mapir"   "$PROJECT_ROOT/data/odm_project_rgb"   "$PROJECT_ROOT/data/odm_project_mapir"   "$PROJECT_ROOT/data/uploads"   "$PROJECT_ROOT/output/ndvi"   "$PROJECT_ROOT/output/runs"   "$PROJECT_ROOT/output/irrigation"   "$PROJECT_ROOT/output/weather"   "$PROJECT_ROOT/runtime/runs"

if [ ! -f "$PROJECT_ROOT/.env" ] && [ -f "$PROJECT_ROOT/.env.example" ]; then
  cp "$PROJECT_ROOT/.env.example" "$PROJECT_ROOT/.env"
  echo "[Config] Created .env from .env.example. Fill in secret values before running weather or irrigation integrations."
fi

echo "[Done] Installation complete."
echo "[Next] Activate the environment: source .venv/bin/activate"
echo "[Next] Verify the setup: python run.py --doctor"
echo "[Next] Start the dashboard: python run.py --serve-dashboard --host 127.0.0.1 --port 8008"
