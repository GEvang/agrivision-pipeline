#!/usr/bin/env bash
set -e

echo "=============================================="
echo "        AgriVision ADS Installer"
echo "=============================================="

# Resolve project root (where this script lives)
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

echo "[System] Project root: $PROJECT_ROOT"

echo
echo "[System] Updating apt..."
sudo apt update

echo
echo "[System] Installing base system packages (Python, GDAL, curl, gnupg)..."
sudo apt install -y \
  python3 python3-venv python3-pip \
  gdal-bin \
  ca-certificates curl gnupg


# ---------------------------------------------------------
# 1) Docker Engine (official repo, only if missing)
# ---------------------------------------------------------
echo
if command -v docker &> /dev/null; then
  echo "[Docker] Docker already installed: $(docker --version)"
else
  echo "[Docker] Docker not found – installing Docker Engine from official repo..."

  # Remove potentially conflicting packages (safe if not present)
  sudo apt remove -y docker.io docker-doc docker-compose podman-docker containerd runc || true

  # Add Docker's official GPG key
  sudo install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
    sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  sudo chmod a+r /etc/apt/keyrings/docker.gpg

  # Add the Docker apt repository
  echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
    https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | \
    sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

  sudo apt update

  # Install Docker Engine + CLI + containerd + compose plugin
  sudo apt install -y \
    docker-ce docker-ce-cli containerd.io \
    docker-buildx-plugin docker-compose-plugin

  echo "[Docker] Installed: $(docker --version)"
fi

echo
echo "[Docker] Ensuring Docker service is enabled and running..."
sudo systemctl enable docker
sudo systemctl start docker


# ---------------------------------------------------------
# 2) Python virtual environment
# ---------------------------------------------------------
echo
echo "[Python] Creating virtual environment (venv)..."
if [ ! -d "venv" ]; then
  python3 -m venv venv
fi

echo "[Python] Activating venv and installing requirements..."
# shellcheck disable=SC1091
source venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt

deactivate


# ---------------------------------------------------------
# 3) Create project folders
# ---------------------------------------------------------
echo
echo "[Folders] Creating AgriVision folder structure..."

mkdir -p data/images_full
mkdir -p data/images_resized
mkdir -p data/odm_project
mkdir -p output/ndvi
mkdir -p output/runs


# ---------------------------------------------------------
# 4) Pull ODM docker image
# ---------------------------------------------------------
echo
echo "[Docker] Pulling ODM image (opendronemap/odm:latest)..."
sudo docker pull opendronemap/odm:latest


# ---------------------------------------------------------
# 5) Clone OpenAgri WeatherService (no YAML modifications)
# ---------------------------------------------------------
echo
echo "[Weather] Cloning OpenAgri-WeatherService (if missing)..."
if [ ! -d "$PROJECT_ROOT/OpenAgri-WeatherService" ]; then
  git clone https://github.com/openagri-eu/OpenAgri-WeatherService.git "$PROJECT_ROOT/OpenAgri-WeatherService"
else
  echo "[Weather] OpenAgri-WeatherService already exists, skipping clone."
fi

echo
echo "[Weather] Attempting to start WeatherService (best effort)..."
cd "$PROJECT_ROOT/OpenAgri-WeatherService"

if [ -f "docker-compose.yml" ]; then
  sudo docker compose up -d || true
else
  echo "[Weather] No default docker-compose.yml found."
  echo "[Weather] This is OK – the AgriVision pipeline will start the correct compose file automatically when needed."
fi

cd "$PROJECT_ROOT"


# ---------------------------------------------------------
# Final message
# ---------------------------------------------------------
echo
echo "=============================================="
echo " AgriVision ADS installation complete!"
echo "=============================================="
echo
echo "To run the pipeline:"
echo "  cd \"$PROJECT_ROOT\""
echo "  source venv/bin/activate"
echo "  python run.py"
echo
echo "Docker Engine is installed and running."
echo "OpenAgri WeatherService will be auto-started by the pipeline if needed."
echo

