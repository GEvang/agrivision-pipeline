#!/usr/bin/env bash
# AgriVision installer script
# Run from the project root: ./install_agrivision.sh

set -e  # exit on first error

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "[AgriVision] Project root: $PROJECT_ROOT"

echo
echo "==============================="
echo "[1/5] Installing system packages (smart check)"
echo "==============================="
echo

# Helper to only install apt packages if they are NOT already installed
install_if_missing() {
  local pkg="$1"
  if dpkg -s "$pkg" >/dev/null 2>&1; then
    echo "[AgriVision] Package '$pkg' already installed, skipping."
  else
    echo "[AgriVision] Installing '$pkg'..."
    sudo apt install -y "$pkg"
  fi
}

echo "[AgriVision] Updating apt package index..."
sudo apt update

# Core Python + GDAL packages
install_if_missing python3
install_if_missing python3-venv
install_if_missing python3-pip
install_if_missing gdal-bin

# Docker handling – be VERY careful to avoid conflicts
if command -v docker >/dev/null 2>&1; then
  echo "[AgriVision] Docker is already installed (docker command found), skipping Docker installation."
else
  # If containerd.io is installed from Docker's official repo, installing docker.io will conflict
  if dpkg -s containerd.io >/dev/null 2>&1; then
    echo "[AgriVision] WARNING: 'containerd.io' is installed (likely from Docker's official repo)."
    echo "[AgriVision] Skipping 'docker.io' installation to avoid conflicts."
    echo "[AgriVision] If Docker is not working, please configure it manually."
  else
    echo "[AgriVision] Docker not found and no containerd.io conflict; installing docker.io..."
    sudo apt install -y docker.io
  fi
fi

echo
echo "[AgriVision] System package step completed."

echo
echo "====================================="
echo "[2/5] Creating data/output structure"
echo "====================================="
echo

mkdir -p "$PROJECT_ROOT/data/images_full"
mkdir -p "$PROJECT_ROOT/data/images_resized"
mkdir -p "$PROJECT_ROOT/data/odm_project"
mkdir -p "$PROJECT_ROOT/output/orthos"
mkdir -p "$PROJECT_ROOT/output/ndvi"
mkdir -p "$PROJECT_ROOT/config"

echo "[AgriVision] Folder structure ensured."

echo
echo "==============================="
echo "[3/5] Creating Python venv"
echo "==============================="
echo

if [ ! -d "$PROJECT_ROOT/venv" ]; then
  python3 -m venv "$PROJECT_ROOT/venv"
  echo "[AgriVision] Virtual environment created at: $PROJECT_ROOT/venv"
else
  echo "[AgriVision] Virtual environment already exists at: $PROJECT_ROOT/venv"
fi

echo
echo "==============================="
echo "[4/5] Installing Python packages"
echo "==============================="
echo

# Activate venv
# shellcheck disable=SC1090
source "$PROJECT_ROOT/venv/bin/activate"

pip install --upgrade pip
pip install pillow rasterio numpy matplotlib

# Write requirements.txt for future installs
pip freeze > "$PROJECT_ROOT/requirements.txt"

echo "[AgriVision] Python packages installed and requirements.txt written."

echo
echo "====================================="
echo "[5/5] Pulling OpenDroneMap Docker image"
echo "====================================="
echo

docker pull opendronemap/odm:latest || {
  echo "[AgriVision] WARNING: Failed to pull opendronemap/odm:latest."
  echo "[AgriVision] Please check your Docker/network configuration."
}

echo
echo "====================================="
echo "[AgriVision] Installation complete!"
echo "====================================="
echo "Next steps:"
echo "  1) If this was the first time adding yourself to the 'docker' group,"
echo "     log out and log back in so Docker works without sudo (if needed)."
echo "  2) Activate the venv before running the pipeline:"
echo "        source venv/bin/activate"
echo "  3) Run the full pipeline with:"
echo "        python3 scripts/ndvi_pipeline.py"
echo

