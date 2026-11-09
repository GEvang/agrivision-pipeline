#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is not installed or not on PATH."
  echo "Install Docker, then run this launcher again."
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "Docker is installed but not running."
  echo "Start Docker, then run this launcher again."
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "docker compose is not available."
  echo "Install the Docker Compose plugin, then run this launcher again."
  exit 1
fi

# With a plain Linux Docker daemon, containers run as root and every file they
# write under the bind mounts would belong to root. Run them as the host user
# instead. Docker Desktop and rootless Docker already map ownership to the user.
docker_os="$(docker info --format '{{.OperatingSystem}}' 2>/dev/null || true)"
docker_security="$(docker info --format '{{json .SecurityOptions}}' 2>/dev/null || true)"
if [[ "$(id -u)" != "0" && "$docker_os" != *"Docker Desktop"* && "$docker_security" != *rootless* ]]; then
  export AGRIVISION_UID="$(id -u)"
  export AGRIVISION_GID="$(id -g)"
  if [[ -S /var/run/docker.sock ]]; then
    export AGRIVISION_DOCKER_GID="$(stat -c %g /var/run/docker.sock)"
  fi
fi

# Create the bind-mounted folders before Docker does, so they belong to the user.
mkdir -p data output runtime/service-helper/logs

if [[ -n "${AGRIVISION_UID:-}" ]]; then
  root_owned=()
  for path in data output runtime runtime/service-helper OpenAgri-WeatherService OpenAgri-IrrigationManagement OpenAgri-PestAndDiseaseManagement; do
    if [[ -e "$path" && ! -O "$path" ]]; then
      root_owned+=("$path")
    fi
  done
  if (( ${#root_owned[@]} )); then
    echo "These folders are owned by another user (usually root from an earlier start):"
    printf '  %s\n' "${root_owned[@]}"
    echo "Give them back to your user, then run this launcher again:"
    echo "  sudo chown -R \"$(id -u):$(id -g)\" ${root_owned[*]}"
    exit 1
  fi
fi

echo "Starting AgriVision dashboard..."
docker compose up --build -d

echo "Starting host service helper..."
chmod +x "$PWD/scripts/service-helper-posix.sh"
nohup "$PWD/scripts/service-helper-posix.sh" >>"$PWD/runtime/service-helper/logs/helper.log" 2>&1 &

echo "AgriVision is available at http://127.0.0.1:8008"
if command -v xdg-open >/dev/null 2>&1; then
  xdg-open "http://127.0.0.1:8008" >/dev/null 2>&1 || true
fi
