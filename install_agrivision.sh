#!/usr/bin/env bash
set -e

echo "==============================="
echo " AgriVision ADS Installer"
echo "==============================="

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "[AgriVision] Project root: $PROJECT_ROOT"

echo
echo "==== [1/7] Install system dependencies (Python, GDAL, etc.) ===="
echo

sudo apt update
sudo apt install -y \
  python3 python3-venv python3-pip \
  gdal-bin

echo
echo "==== [2/7] Check Docker installation ===="
echo

if ! command -v docker &> /dev/null; then
    echo "[Docker] Docker not found. Installing Ubuntu docker.io + compose plugin..."
    sudo apt install -y docker.io docker-compose-plugin
else
    echo "[Docker] Docker installed: $(docker --version)"
fi

if ! docker compose version &> /dev/null; then
    echo "[Docker] Docker compose plugin missing. Installing..."
    sudo apt install -y docker-compose-plugin
else
    echo "[Docker] Docker compose plugin available."
fi

echo
echo "==== [3/7] Ensure Docker is running ===="
echo

sudo systemctl enable docker
sudo systemctl start docker

echo "[Docker] Status:"
sudo systemctl --no-pager --full status docker || true

echo
echo "==== [4/7] Create Python virtual environment ===="
echo

cd "$PROJECT_ROOT"

if [ ! -d "venv" ]; then
  python3 -m venv venv
fi

# shellcheck disable=SC1090
source venv/bin/activate

pip install --upgrade pip
pip install pillow rasterio numpy matplotlib pyyaml requests

pip freeze > requirements.txt

echo
echo "==== [5/7] Prepare data/output folders ===="
echo

mkdir -p data/images_full
mkdir -p data/images_resized
mkdir -p data/odm_project
mkdir -p output/ndvi
mkdir -p output/runs

echo
echo "==== [6/7] Pull ODM Docker image ===="
echo

sudo docker pull opendronemap/odm:latest

echo
echo "==== [7/7] Install + Configure OpenAgri WeatherService ===="
echo

cd "$PROJECT_ROOT"

if [ ! -d "OpenAgri-WeatherService" ]; then
    echo "[Weather] Cloning OpenAgri-WeatherService..."
    git clone https://github.com/agstack/OpenAgri-WeatherService.git OpenAgri-WeatherService
else
    echo "[Weather] Already exists, skipping clone."
fi

echo "[Weather] Creating docker-compose.override.yml..."

cat <<EOF > "$PROJECT_ROOT/OpenAgri-WeatherService/docker-compose.override.yml"
sudo docker compose up -d

echo
echo "======================================"
echo " AgriVision installation complete! 🎉"
echo "======================================"
echo
echo "To run the pipeline:"
echo "  cd $PROJECT_ROOT"
echo "  source venv/bin/activate"
echo "  python run.py"
echo

