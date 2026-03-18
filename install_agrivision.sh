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

mkdir -p data
mkdir -p data/images_full/rgb data/images_full/mapir
mkdir -p data/images_resized/rgb data/images_resized/mapir
mkdir -p data/odm_project_rgb data/odm_project_mapir
mkdir -p output/ndvi output/runs


# ---------------------------------------------------------
# 4) Pull ODM docker image
# ---------------------------------------------------------
echo
echo "[Docker] Pulling ODM image (opendronemap/odm:latest)..."
sudo docker pull opendronemap/odm:latest


# ---------------------------------------------------------
# 5) Clone + prepare OpenAgri WeatherService
# ---------------------------------------------------------
echo
echo "[Weather] Cloning OpenAgri-WeatherService (if missing)..."
if [ ! -d "$PROJECT_ROOT/OpenAgri-WeatherService" ]; then
  git clone https://github.com/openagri-eu/OpenAgri-WeatherService.git "$PROJECT_ROOT/OpenAgri-WeatherService"
else
  echo "[Weather] OpenAgri-WeatherService already exists, skipping clone."
fi

# Ensure .env exists
if [ ! -f "$PROJECT_ROOT/OpenAgri-WeatherService/.env" ]; then
  echo "[Weather] No .env found, copying env.example -> .env"
  cp "$PROJECT_ROOT/OpenAgri-WeatherService/env.example" \
     "$PROJECT_ROOT/OpenAgri-WeatherService/.env"
fi

echo
echo "[Weather] Starting WeatherService..."

cd "$PROJECT_ROOT/OpenAgri-WeatherService"

ARCH=$(uname -m)
COMPOSE_FILE=""

if [ "$ARCH" = "x86_64" ]; then
  COMPOSE_FILE="docker-compose-x86_64.yml"
elif [[ "$ARCH" == "aarch64" || "$ARCH" == "arm64" ]]; then
  COMPOSE_FILE="docker-compose-arm64.yml"
else
  echo "[Weather] Unknown architecture '$ARCH'. Cannot auto-select compose file."
  echo "[Weather] WeatherService will instead be started automatically by the pipeline when needed."
fi

if [ -n "$COMPOSE_FILE" ]; then
  if [ -f "$COMPOSE_FILE" ]; then
    echo "[Weather] Using compose file: $COMPOSE_FILE"
    sudo docker compose -f "$COMPOSE_FILE" up -d || true
  else
    echo "[Weather] Compose file '$COMPOSE_FILE' not found!"
    echo "[Weather] WeatherService will be started automatically by the pipeline when needed."
  fi
fi

cd "$PROJECT_ROOT"


# ---------------------------------------------------------
# 6) Clone + prepare OpenAgri Irrigation Management Service
# ---------------------------------------------------------
echo
echo "[Irrigation] Cloning OpenAgri-IrrigationManagement (if missing)..."
if [ ! -d "$PROJECT_ROOT/OpenAgri-IrrigationManagement" ]; then
  git clone https://github.com/agstack/OpenAgri-IrrigationManagement.git "$PROJECT_ROOT/OpenAgri-IrrigationManagement"
else
  echo "[Irrigation] OpenAgri-IrrigationManagement already exists, skipping clone."
fi

echo
echo "[Irrigation] Preparing environment (.env) and starting service..."

cd "$PROJECT_ROOT/OpenAgri-IrrigationManagement"

# Pick compose filename
IRR_COMPOSE_FILE=""
if [ -f "docker-compose.yml" ]; then
  IRR_COMPOSE_FILE="docker-compose.yml"
elif [ -f "docker-compose.yaml" ]; then
  IRR_COMPOSE_FILE="docker-compose.yaml"
elif [ -f "compose.yml" ]; then
  IRR_COMPOSE_FILE="compose.yml"
elif [ -f "compose.yaml" ]; then
  IRR_COMPOSE_FILE="compose.yaml"
fi

if [ -z "$IRR_COMPOSE_FILE" ]; then
  echo "[Irrigation] ERROR: No docker compose file found."
  echo "[Irrigation] Expected one of: docker-compose.yml / docker-compose.yaml / compose.yml / compose.yaml"
  exit 1
fi

echo "[Irrigation] Using compose file: $IRR_COMPOSE_FILE"

# Ensure .env exists (compose.yaml uses env vars; missing values break port mappings)
if [ ! -f ".env" ]; then
  echo "[Irrigation] No .env found. Creating one..."

  # Try to copy from common template names if they exist
  if [ -f "env.example" ]; then
    cp "env.example" ".env"
    echo "[Irrigation] Copied env.example -> .env"
  elif [ -f ".env.example" ]; then
    cp ".env.example" ".env"
    echo "[Irrigation] Copied .env.example -> .env"
  else
    # Create minimal .env if no template exists
    cat > ".env" <<'EOF'
# Auto-generated by AgriVision installer
EOF
    echo "[Irrigation] Created minimal .env"
  fi
fi

# Helper: set KEY=VALUE in .env (replace if exists, append if missing)
set_env_var () {
  local key="$1"
  local value="$2"
  if grep -qE "^${key}=" ".env"; then
    # replace existing
    sed -i "s|^${key}=.*|${key}=${value}|" ".env"
  else
    # append
    echo "${key}=${value}" >> ".env"
  fi
}

# REQUIRED defaults (these remove the warnings you saw and prevent "invalid proto")
# Port: you specified 8004 as the default in the docs and your config.
set_env_var "SERVICE_PORT" "8004"

# Postgres defaults (typical compose service name is 'postgres')
set_env_var "POSTGRES_HOST" "postgres"
set_env_var "POSTGRES_PORT" "5432"
set_env_var "POSTGRES_USER" "postgres"
set_env_var "POSTGRES_PASSWORD" "postgres"
set_env_var "POSTGRES_DB" "irrigation"

echo "[Irrigation] Final .env key values (sanity):"
grep -E "^(SERVICE_PORT|POSTGRES_HOST|POSTGRES_PORT|POSTGRES_USER|POSTGRES_PASSWORD|POSTGRES_DB)=" ".env" || true

# Start service
sudo docker compose -f "$IRR_COMPOSE_FILE" up -d

cd "$PROJECT_ROOT"

# Health check (FastAPI)
echo
echo "[Irrigation] Waiting for Irrigation API to become available on http://127.0.0.1:8004 ..."

IRR_BASE="http://127.0.0.1:8004"
OK=0

for i in {1..45}; do
  if curl -fsS "$IRR_BASE/openapi.json" > /dev/null 2>&1; then
    OK=1
    break
  fi
  if curl -fsS "$IRR_BASE/docs" > /dev/null 2>&1; then
    OK=1
    break
  fi
  sleep 1
done

if [ "$OK" -eq 1 ]; then
  echo "[Irrigation] ✅ Irrigation API is reachable: $IRR_BASE"
else
  echo "[Irrigation] ❌ Irrigation API did not become reachable on $IRR_BASE"
  echo "[Irrigation] Showing container status + recent logs (best effort)..."
  sudo docker ps || true
  (cd "$PROJECT_ROOT/OpenAgri-IrrigationManagement" && sudo docker compose -f "$IRR_COMPOSE_FILE" logs --tail=160) || true
  exit 1
fi

echo
echo "=============================================="
echo "   Installation complete (system + services)"
echo "=============================================="
