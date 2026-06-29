#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
HELPER_DIR="$ROOT_DIR/runtime/service-helper"
COMMANDS_DIR="$HELPER_DIR/commands"
RESPONSES_DIR="$HELPER_DIR/responses"
LOGS_DIR="$HELPER_DIR/logs"
SERVICES_DIR="$HELPER_DIR/services"
WORK_DIR="$HELPER_DIR/work"
PID_FILE="$HELPER_DIR/helper.pid"

mkdir -p "$COMMANDS_DIR" "$RESPONSES_DIR" "$LOGS_DIR" "$SERVICES_DIR" "$WORK_DIR"

if [[ -f "$PID_FILE" ]]; then
  existing_pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [[ -n "$existing_pid" ]] && kill -0 "$existing_pid" 2>/dev/null; then
    exit 0
  fi
fi

echo "$$" >"$PID_FILE"
trap 'rm -f "$PID_FILE"' EXIT

docker_run_prepare() {
  local service_key="$1"
  docker run --rm \
    -v "$ROOT_DIR:/workspace" \
    -w /workspace \
    -e AGRIVISION_PROJECT_ROOT=/workspace \
    -e AGRIVISION_CONFIG_PATH=/workspace/config.yaml \
    -e AGRIVISION_RUNTIME_SETTINGS_PATH=/workspace/runtime/settings.json \
    agrivision-pipeline:phase5 \
    python run.py --service-control --service-key "$service_key" --service-action prepare
}

repo_dir_for() {
  case "$1" in
    weather) printf '%s\n' "$ROOT_DIR/OpenAgri-WeatherService" ;;
    irrigation) printf '%s\n' "$ROOT_DIR/OpenAgri-IrrigationManagement" ;;
    pdm) printf '%s\n' "$ROOT_DIR/OpenAgri-PestAndDiseaseManagement" ;;
    *) return 1 ;;
  esac
}

compose_file_for() {
  local service_key="$1"
  local repo_dir="$2"
  local candidates=()
  case "$service_key" in
    weather)
      if [[ "$(uname -m)" == "aarch64" || "$(uname -m)" == "arm64" ]]; then
        candidates=("docker-compose-arm64.yml" "docker-compose-x86_64.yml" "docker-compose.yml" "docker-compose.yaml")
      else
        candidates=("docker-compose-x86_64.yml" "docker-compose-arm64.yml" "docker-compose.yml" "docker-compose.yaml")
      fi
      ;;
    irrigation|pdm)
      candidates=("compose.yaml" "compose.yml" "docker-compose.yml" "docker-compose.yaml")
      ;;
  esac
  local candidate
  for candidate in "${candidates[@]}"; do
    if [[ -f "$repo_dir/$candidate" ]]; then
      printf '%s\n' "$repo_dir/$candidate"
      return 0
    fi
  done
  return 1
}

write_service_state() {
  local service_key="$1"
  local repo_dir
  repo_dir="$(repo_dir_for "$service_key")"
  local state_file="$SERVICES_DIR/$service_key.env"
  local installed="0"
  local compose_file=""
  if [[ -d "$repo_dir" ]]; then
    installed="1"
    compose_file="$(compose_file_for "$service_key" "$repo_dir" || true)"
  fi
  {
    printf 'INSTALLED=%s\n' "$installed"
    printf 'REPO_DIR=%s\n' "$repo_dir"
    printf 'COMPOSE_FILE=%s\n' "$compose_file"
  } >"$state_file"
}

write_helper_status() {
  {
    printf 'TIMESTAMP_EPOCH=%s\n' "$(date +%s)"
    printf 'MODE=host-launcher\n'
  } >"$HELPER_DIR/helper.env"
}

compose_up_args_for() {
  case "$1" in
    weather) printf '%s\n' "up -d" ;;
    irrigation) printf '%s\n' "up -d --build" ;;
    pdm) printf '%s\n' "up -d" ;;
    *) return 1 ;;
  esac
}

compose_restart_args_for() {
  case "$1" in
    weather) printf '%s\n' "up -d --force-recreate" ;;
    irrigation) printf '%s\n' "up -d --build --force-recreate" ;;
    pdm) printf '%s\n' "up -d --force-recreate" ;;
    *) return 1 ;;
  esac
}

ensure_service_host() {
  local service_key="$1"
  docker_run_prepare "$service_key"
  local repo_dir
  repo_dir="$(repo_dir_for "$service_key")"
  local compose_file
  compose_file="$(compose_file_for "$service_key" "$repo_dir")"
  local args
  args="$(compose_up_args_for "$service_key")"
  (
    cd "$repo_dir"
    docker compose -f "$compose_file" $args
  )
}

restart_service_host() {
  local service_key="$1"
  docker_run_prepare "$service_key"
  local repo_dir
  repo_dir="$(repo_dir_for "$service_key")"
  local compose_file
  compose_file="$(compose_file_for "$service_key" "$repo_dir")"
  local args
  args="$(compose_restart_args_for "$service_key")"
  (
    cd "$repo_dir"
    docker compose -f "$compose_file" $args
  )
}

stop_service_host() {
  local service_key="$1"
  local repo_dir
  repo_dir="$(repo_dir_for "$service_key")"
  local compose_file
  compose_file="$(compose_file_for "$service_key" "$repo_dir")"
  (
    cd "$repo_dir"
    docker compose -f "$compose_file" stop
  )
}

install_missing_services_host() {
  local service_key
  for service_key in weather irrigation pdm; do
    write_service_state "$service_key"
    if ! grep -q '^INSTALLED=1$' "$SERVICES_DIR/$service_key.env"; then
      ensure_service_host "$service_key"
    fi
  done
}

process_command() {
  local command_path="$1"
  local request_id="" action="" service_key=""
  while IFS='=' read -r key value; do
    case "$key" in
      REQUEST_ID) request_id="$value" ;;
      ACTION) action="$value" ;;
      SERVICE_KEY) service_key="$value" ;;
    esac
  done <"$command_path"

  local log_path="$LOGS_DIR/${request_id}.log"
  local response_path="$RESPONSES_DIR/${request_id}.env"
  local ok="1"
  local message="Completed."

  {
    echo "[host-helper] ACTION=$action SERVICE_KEY=$service_key"
    case "$action" in
      install_missing) install_missing_services_host ;;
      ensure) ensure_service_host "$service_key" ;;
      restart) restart_service_host "$service_key" ;;
      stop) stop_service_host "$service_key" ;;
      *)
        echo "Unknown action: $action" >&2
        return 2
        ;;
    esac
  } >"$log_path" 2>&1 || {
    ok="0"
    message="Host helper failed while running $action ${service_key:-}."
  }

  for service_key in weather irrigation pdm; do
    write_service_state "$service_key"
  done

  {
    printf 'REQUEST_ID=%s\n' "$request_id"
    printf 'OK=%s\n' "$ok"
    printf 'MESSAGE=%s\n' "$message"
    printf 'LOG_PATH=%s\n' "$log_path"
  } >"$response_path"
}

for service_key in weather irrigation pdm; do
  write_service_state "$service_key"
done

while true; do
  write_helper_status
  for service_key in weather irrigation pdm; do
    write_service_state "$service_key"
  done
  shopt -s nullglob
  for command_path in "$COMMANDS_DIR"/*.env; do
    working_path="$WORK_DIR/$(basename "$command_path")"
    mv "$command_path" "$working_path"
    process_command "$working_path"
    rm -f "$working_path"
  done
  shopt -u nullglob
  sleep 2
done
