#!/usr/bin/env bash
set -euo pipefail

echo "==== AgriVision ADS One-Line Installer ===="

sudo apt update
sudo apt install -y git

TARGET_DIR="${1:-agrivision-ads}"

if [ ! -d "$TARGET_DIR" ]; then
  git clone https://github.com/GEvang/agrivision-pipeline.git "$TARGET_DIR"
fi

cd "$TARGET_DIR"
chmod +x deployment/scripts/install.sh
./deployment/scripts/install.sh

echo "==== Installation Complete ===="
echo "To run the pipeline:"
echo "  cd $(pwd)"
echo "  source venv/bin/activate"
echo "  python run.py"
echo "To run with Docker from the repo root:"
echo "  docker compose -f deployment/docker/docker-compose.yml up --build"
