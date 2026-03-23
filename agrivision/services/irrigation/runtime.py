from __future__ import annotations

from pathlib import Path

import requests

from agrivision.config.settings import get_settings
from agrivision.services.runtime import (
    ServiceBootstrapError,
    base_env_values,
    clone_repo_if_missing,
    compose_up,
    detect_compose_file,
    ensure_env_file,
    project_service_dir,
    update_env_file,
    wait_for_any_url,
)

IRRIGATION_REPO_URL = "https://github.com/agstack/OpenAgri-IrrigationManagement.git"


def _service_dir() -> Path:
    settings = get_settings()
    return project_service_dir(settings.irrigation.service_dir or "OpenAgri-IrrigationManagement")


def _env_values() -> dict[str, str]:
    settings = get_settings()
    port = str(settings.irrigation.base_url.rsplit(":", 1)[-1])
    values = base_env_values()
    values.update(
        {
            "SOURCE_REPO": "openagri-eu/openagri-irrigationmanagement",
            "SERVICE_PORT": port,
            "PORT": port,
            "IRRIGATION_PORT": port,
            "POSTGRES_HOST": "db",
            "POSTGRES_PORT": "5432",
            "POSTGRES_USER": "postgres",
            "POSTGRES_PASSWORD": "postgres",
            "POSTGRES_DB": "irrigation",
            "DB_HOST": "db",
            "DB_PORT": "5432",
            "DB_USER": "postgres",
            "DB_PASSWORD": "postgres",
            "DB_NAME": "irrigation",
            "IRRIGATION_SUPERUSER_EMAIL": settings.irrigation.auth.email or "",
            "IRRIGATION_SUPERUSER_PASSWORD": settings.irrigation.auth.password or "",
        }
    )
    return values


def ensure_repo_and_env() -> tuple[Path, Path, Path]:
    repo_dir = _service_dir()
    clone_repo_if_missing(repo_dir, IRRIGATION_REPO_URL)
    env_path = ensure_env_file(repo_dir)
    update_env_file(env_path, _env_values())
    compose_file = detect_compose_file(repo_dir)
    return repo_dir, env_path, compose_file


def start_service_if_needed(timeout_seconds: int = 90) -> None:
    settings = get_settings()
    health_urls = [
        f"{settings.irrigation.base_url}/openapi.json",
        f"{settings.irrigation.base_url}/docs",
        f"{settings.irrigation.base_url}/api/v1/openapi.json",
    ]
    for url in health_urls:
        try:
            response = requests.get(url, timeout=3)
            if response.status_code < 500:
                return
        except requests.RequestException:
            pass

    repo_dir, _, compose_file = ensure_repo_and_env()
    compose_up(compose_file, repo_dir)
    if not wait_for_any_url(health_urls, timeout_seconds=timeout_seconds):
        raise ServiceBootstrapError(
            f"Irrigation service did not become reachable at {settings.irrigation.base_url}"
        )
