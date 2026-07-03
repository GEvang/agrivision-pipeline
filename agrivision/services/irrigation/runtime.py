from __future__ import annotations

import os
from pathlib import Path

from agrivision.config.settings import get_settings
from agrivision.services.runtime import (
    EnvSyncResult,
    ServiceBootstrapError,
    ServiceRuntimeState,
    base_env_values,
    clone_repo_if_missing,
    ensure_env_file,
    inspect_external_service_runtime,
    project_service_dir,
    reconcile_service_runtime,
    summarize_env_changes,
    update_env_file,
)

IRRIGATION_REPO_URL = "https://github.com/openagri-eu/OpenAgri-IrrigationManagement.git"
DEFAULT_SERVICE_USERNAME = "dummy@email.com"
DEFAULT_SERVICE_PASSWORD = "StrongPass1@"


def _service_dir() -> Path:
    settings = get_settings()
    return project_service_dir(settings.irrigation.service_dir or "OpenAgri-IrrigationManagement")


def _apply_compatibility_patches(repo_dir: Path) -> None:
    entrypoint_path = repo_dir / "entrypoint.sh"
    if entrypoint_path.exists():
        entrypoint = entrypoint_path.read_bytes()
        normalized = entrypoint.replace(b"\r\n", b"\n")
        if normalized != entrypoint:
            entrypoint_path.write_bytes(normalized)

    main_path = repo_dir / "app" / "main.py"
    if not main_path.exists():
        return

    text = main_path.read_text(encoding="utf-8")
    imports: list[str] = []
    if "import logging" not in text:
        imports.append("import logging")
    if "import time" not in text:
        imports.append("import time")
    if not imports:
        return

    main_path.write_text("\n".join(imports) + "\n" + text, encoding="utf-8")


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
            "IRRIGATION_SUPERUSER_EMAIL": settings.irrigation.auth.email or DEFAULT_SERVICE_USERNAME,
            "IRRIGATION_SUPERUSER_PASSWORD": settings.irrigation.auth.password or DEFAULT_SERVICE_PASSWORD,
        }
    )
    return values


def ensure_repo_and_env(timeout_seconds: int = 90) -> ServiceRuntimeState:
    settings = get_settings()
    repo_dir = _service_dir()
    health_urls = [
        f"{settings.irrigation.base_url}/openapi.json",
        f"{settings.irrigation.base_url}/docs",
        f"{settings.irrigation.base_url}/api/v1/openapi.json",
    ]
    if os.getenv("APP_CONTAINER_PROJECT_ROOT", "").strip():
        return inspect_external_service_runtime(
            repo_dir=repo_dir,
            readiness_urls=health_urls,
            timeout_seconds=timeout_seconds,
        )
    clone_repo_if_missing(repo_dir, IRRIGATION_REPO_URL)
    _apply_compatibility_patches(repo_dir)
    return reconcile_service_runtime(
        repo_dir=repo_dir,
        repo_url=IRRIGATION_REPO_URL,
        env_values=_env_values(),
        compose_candidates=None,
        readiness_urls=health_urls,
        timeout_seconds=timeout_seconds,
        build_on_recreate=True,
    )


def prepare_repo_and_env() -> EnvSyncResult:
    repo_dir = _service_dir()
    clone_repo_if_missing(repo_dir, IRRIGATION_REPO_URL)
    _apply_compatibility_patches(repo_dir)
    env_path = ensure_env_file(repo_dir)
    return update_env_file(env_path, _env_values())


def ensure_service_available(timeout_seconds: int = 90, verbose: bool = True) -> ServiceRuntimeState:
    settings = get_settings()
    state = ensure_repo_and_env(timeout_seconds=timeout_seconds)
    if verbose and state.env_sync.changed:
        for line in summarize_env_changes(_env_values(), state.env_sync):
            print(f"[Irrigation] {line}")
    if not state.ready:
        raise ServiceBootstrapError(
            f"Irrigation service did not become reachable at {settings.irrigation.base_url}"
        )
    return state


# Backward-compatible alias for older callers.
def start_service_if_needed(timeout_seconds: int = 90) -> None:
    ensure_service_available(timeout_seconds=timeout_seconds, verbose=True)
