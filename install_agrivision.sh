#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

printf '
=== AgriVision Pipeline installer ===
'
printf '[Info] Project root: %s
' "$PROJECT_ROOT"

if ! command -v python3 >/dev/null 2>&1; then
  echo '[Error] python3 is required but was not found.' >&2
  exit 1
fi

if ! command -v gdalinfo >/dev/null 2>&1; then
  echo '[Warn] gdalinfo was not found. Install GDAL system packages before running orthophoto or raster steps.'
fi

if [ ! -d .venv ]; then
  python3 -m venv .venv
  echo '[Info] Created .venv'
else
  echo '[Info] Reusing existing .venv'
fi

# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
python -m pip install -e ".[dev]"

mkdir -p   data/images_full/rgb   data/images_full/mapir   data/images_resized/rgb   data/images_resized/mapir   data/odm_project_rgb   data/odm_project_mapir   output/ndvi   output/runs   output/irrigation   output/weather   runtime/runs

if [ ! -f .env ]; then
  if [ -f .env.example ]; then
    cp .env.example .env
    echo '[Info] Created .env from .env.example'
  else
    : > .env
    echo '[Info] Created empty .env'
  fi
fi

echo '[Done] Installation complete.'
echo '[Next] Activate the environment with: source .venv/bin/activate'
echo '[Next] Validate the setup with: python run.py --doctor'
