from __future__ import annotations

from pathlib import Path

from agrivision.config.settings import get_settings
from agrivision.services.runtime import (
    ServiceBootstrapError,
    ServiceRuntimeState,
    base_env_values,
    project_service_dir,
    reconcile_service_runtime,
    summarize_env_changes,
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


def ensure_repo_and_env(timeout_seconds: int = 90) -> ServiceRuntimeState:
    settings = get_settings()
    health_urls = [
        f"{settings.irrigation.base_url}/openapi.json",
        f"{settings.irrigation.base_url}/docs",
        f"{settings.irrigation.base_url}/api/v1/openapi.json",
    ]
    return reconcile_service_runtime(
        repo_dir=_service_dir(),
        repo_url=IRRIGATION_REPO_URL,
        env_values=_env_values(),
        compose_candidates=None,
        readiness_urls=health_urls,
        timeout_seconds=timeout_seconds,
    )


def start_service_if_needed(timeout_seconds: int = 90) -> None:
    settings = get_settings()
    state = ensure_repo_and_env(timeout_seconds=timeout_seconds)
    if state.env_sync.changed:
        for line in summarize_env_changes(_env_values(), state.env_sync):
            print(f"[Irrigation] {line}")
    if not state.ready:
        raise ServiceBootstrapError(
            f"Irrigation service did not become reachable at {settings.irrigation.base_url}"
        )
