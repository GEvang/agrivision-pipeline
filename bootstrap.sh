#!/usr/bin/env bash
set -e

echo "==== AgriVision ADS One-Line Installer ===="

# 1) Make sure git is present
sudo apt update
sudo apt install -y git

# 2) Clone ADS repo if it doesn't exist yet
if [ ! -d "agrivision-ads" ]; then
    git clone https://github.com/GEvang/agrivision-pipeline.git
fi

cd agrivision-ads

# 3) Run the main installer inside the repo
chmod +x install_agrivision.sh
./install_agrivision.sh

echo "==== Installation Complete ===="
echo "To run the pipeline:"
echo "  cd ~/agrivision-ads"
echo "  source venv/bin/activate"
echo "  python run.py"

