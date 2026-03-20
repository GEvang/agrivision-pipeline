from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import requests

from agrivision.config.settings import get_project_root, load_config
from agrivision.services.runtime import (
    clone_repo_if_missing,
    compose_up,
    ensure_env_file,
    find_existing_file,
    parse_port_from_base_url,
    upsert_env_values,
    wait_for_http,
)

IRRIGATION_REPO_URL = "https://github.com/agstack/OpenAgri-IrrigationManagement.git"
IRRIGATION_COMPOSE_CANDIDATES = [
    "compose.yaml",
    "compose.yml",
    "docker-compose.yml",
    "docker-compose.yaml",
]
IRRIGATION_ENV_TEMPLATES = ["env.example", ".env.example"]


def get_irrigation_settings() -> dict[str, Any]:
    config = load_config()
    irrigation_cfg = config.get("irrigation", {}) or {}
    auth_cfg = irrigation_cfg.get("auth", {}) or {}
    timeout_raw = irrigation_cfg.get("timeout_seconds", 20)
    try:
        timeout_seconds = int(timeout_raw)
    except (TypeError, ValueError):
        timeout_seconds = 20

    return {
        "base_url": str(irrigation_cfg.get("base_url") or "").rstrip("/"),
        "timeout_seconds": timeout_seconds,
        "email": str(auth_cfg.get("email") or os.getenv("IRRIGATION_EMAIL") or ""),
        "password": str(auth_cfg.get("password") or os.getenv("IRRIGATION_PASSWORD") or ""),
        "service_dirname": str(irrigation_cfg.get("service_dir") or "OpenAgri-IrrigationManagement"),
        "default_parcel_wkt": irrigation_cfg.get("default_parcel_wkt"),
        "token": irrigation_cfg.get("token"),
    }


def service_dir() -> Path:
    return get_project_root() / get_irrigation_settings()["service_dirname"]


def _env_values() -> dict[str, str]:
    settings = get_irrigation_settings()
    port = parse_port_from_base_url(settings["base_url"], 8004)
    return {
        "SERVICE_PORT": str(port),
        "POSTGRES_HOST": "postgres",
        "POSTGRES_PORT": "5432",
        "POSTGRES_USER": "postgres",
        "POSTGRES_PASSWORD": "postgres",
        "POSTGRES_DB": "irrigation",
    }


def ensure_repo_and_env() -> tuple[Path, Path]:
    repo_dir = service_dir()
    clone_repo_if_missing(repo_dir, IRRIGATION_REPO_URL)
    env_path = ensure_env_file(repo_dir, IRRIGATION_ENV_TEMPLATES)
    upsert_env_values(env_path, _env_values())
    compose_file = find_existing_file(repo_dir, IRRIGATION_COMPOSE_CANDIDATES)
    if compose_file is None:
        raise FileNotFoundError(
            f"No irrigation compose file found in {repo_dir}. "
            f"Expected one of: {', '.join(IRRIGATION_COMPOSE_CANDIDATES)}"
        )
    return repo_dir, compose_file


def service_is_up(base_url: str) -> bool:
    docs_candidates = [
        f"{base_url}/docs",
        f"{base_url}/api/v1/openapi.json",
    ]
    for url in docs_candidates:
        try:
            response = requests.get(url, timeout=3)
            if 200 <= response.status_code < 500:
                return True
        except requests.RequestException:
            continue
    return False


def start_service_if_needed(verbose: bool = True) -> None:
    settings = get_irrigation_settings()
    base_url = settings["base_url"]
    if service_is_up(base_url):
        return
    repo_dir, compose_file = ensure_repo_and_env()
    if verbose:
        print(f"[Irrigation] Service not reachable. Starting stack from {compose_file} ...")
    compose_up(repo_dir, compose_file, force_recreate=True)
    if not wait_for_http(f"{base_url}/docs", seconds=90, interval=2.0):
        if not wait_for_http(f"{base_url}/api/v1/openapi.json", seconds=30, interval=2.0):
            raise RuntimeError(
                "Irrigation service did not become reachable after docker compose up. "
                "Check docker ps and irrigation container logs."
            )
