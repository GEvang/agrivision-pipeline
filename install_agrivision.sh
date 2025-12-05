#!/usr/bin/env bash
set -e

echo "=============================================="
echo "        AgriVision ADS Installer"
echo "=============================================="

PROJECT_ROOT="$(pwd)"

echo "[System] Updating apt..."
sudo apt update

echo "[System] Installing Python, GDAL, Docker prerequisites..."
sudo apt install -y python3 python3-venv python3-pip gdal-bin docker.io docker-compose-plugin

echo "[System] Ensuring Docker service is enabled..."
sudo systemctl enable docker
sudo systemctl start docker


# ---------------------------------------------------------
# 1) Python virtual environment
# ---------------------------------------------------------
echo
echo "[Python] Creating virtual environment..."
python3 -m venv venv

echo "[Python] Activating venv and installing requirements..."
source venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt

deactivate


# ---------------------------------------------------------
# 2) Create project folders
# ---------------------------------------------------------
echo
echo "[Folders] Creating AgriVision folder structure..."

mkdir -p data/images_full
mkdir -p data/images_resized
mkdir -p data/odm_project
mkdir -p output/ndvi
mkdir -p output/runs


# ---------------------------------------------------------
# 3) Pull ODM docker image
# ---------------------------------------------------------
echo
echo "[Docker] Pulling ODM image..."
sudo docker pull opendronemap/odm:latest


# ---------------------------------------------------------
# 4) Clone OpenAgri WeatherService
# ---------------------------------------------------------
echo
echo "[Weather] Cloning OpenAgri-WeatherService..."
if [ ! -d "OpenAgri-WeatherService" ]; then
    git clone https://github.com/openagri-eu/OpenAgri-WeatherService.git
else
    echo "[Weather] Already exists, skipping clone."
fi


# ---------------------------------------------------------
# 5) DO NOT modify their docker-compose files.
#    User will run the correct compose file manually or via auto-start logic.
# ---------------------------------------------------------

echo
echo "[Weather] Starting WeatherService using docker compose (default try)..."
cd "$PROJECT_ROOT/OpenAgri-WeatherService" || exit 1

# Try the default file (may fail; ADS auto-start script will handle x86_64)
sudo docker compose up -d || true

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
echo "If WeatherService is not running, your pipeline"
echo "will automatically start it using the correct compose file."
echo

