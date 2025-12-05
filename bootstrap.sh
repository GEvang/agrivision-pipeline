#!/usr/bin/env bash
set -e

echo "==== AgriVision ADS One-Line Installer ===="

sudo apt update
sudo apt install -y git

# Clone into consistent folder name:
if [ ! -d "agrivision-ads" ]; then
    git clone https://github.com/GEvang/agrivision-pipeline.git agrivision-ads
fi

cd agrivision-ads

chmod +x install_agrivision.sh
./install_agrivision.sh

echo "==== Installation Complete ===="
echo "To run the pipeline:"
echo "  cd ~/agrivision-ads"
echo "  source venv/bin/activate"
echo "  python run.py"

