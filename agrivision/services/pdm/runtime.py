from __future__ import annotations

from pathlib import Path

from agrivision.config.settings import get_settings
from agrivision.services.runtime import (
    EnvSyncResult,
    ServiceBootstrapError,
    ServiceRuntimeState,
    base_env_values,
    clone_repo_if_missing,
    ensure_env_file,
    project_service_dir,
    reconcile_service_runtime,
    summarize_env_changes,
    update_env_file,
)

PDM_REPO_URL = "https://github.com/openagri-eu/OpenAgri-PestAndDiseaseManagement.git"


def _service_dir() -> Path:
    settings = get_settings()
    service_dir = getattr(settings.pdm, 'service_dir', None) or 'OpenAgri-PestAndDiseaseManagement'
    return project_service_dir(service_dir)


def _env_values() -> dict[str, str]:
    settings = get_settings()
    port = str(settings.pdm.base_url.rsplit(':', 1)[-1])
    values = base_env_values()
    values.update(
        {
            'SERVICE_PORT': port,
            'PORT': port,
            'POSTGRES_HOST': 'db',
            'POSTGRES_PORT': '5432',
            'POSTGRES_USER': 'postgres',
            'POSTGRES_PASSWORD': 'postgres',
            'POSTGRES_DB': 'pdm',
            'JWT_KEY': 'agrivision-pdm-dev-jwt-key',
            'ACCESS_TOKEN_EXPIRATION_TIME': '240',
            'REFRESH_TOKEN_EXPIRATION_TIME': '1600',
            'JWT_ALGORITHM': 'HS256',
            'USING_GATEKEEPER': 'False',
            'SERVICE_NAME': 'pdm',
            'CORS_ORIGINS': '["*"]',
            'LOGGING': 'DEBUG',
            'GATEKEEPER_BASE_URL': 'http://127.0.0.1:8001',
            'GATEKEEPER_USERNAME': settings.pdm.auth.username or 'admin',
            'GATEKEEPER_PASSWORD': settings.pdm.auth.password or 'admin',
        }
    )
    return values


def ensure_repo_and_env(timeout_seconds: int = 120) -> ServiceRuntimeState:
    settings = get_settings()
    health_urls = [
        f"{settings.pdm.base_url}/openapi.json",
        f"{settings.pdm.base_url}/docs",
        f"{settings.pdm.base_url}/health",
        f"{settings.pdm.base_url}/api/v1/openapi.json",
    ]
    return reconcile_service_runtime(
        repo_dir=_service_dir(),
        repo_url=PDM_REPO_URL,
        env_values=_env_values(),
        compose_candidates=['compose.yaml', 'docker-compose.yml', 'docker-compose.yaml'],
        readiness_urls=health_urls,
        timeout_seconds=timeout_seconds,
        build_on_recreate=False,
    )


def prepare_repo_and_env() -> EnvSyncResult:
    repo_dir = _service_dir()
    clone_repo_if_missing(repo_dir, PDM_REPO_URL)
    env_path = ensure_env_file(repo_dir)
    return update_env_file(env_path, _env_values())


def ensure_service_available(timeout_seconds: int = 120, verbose: bool = True) -> ServiceRuntimeState:
    settings = get_settings()
    state = ensure_repo_and_env(timeout_seconds=timeout_seconds)
    if verbose and state.env_sync.changed:
        for line in summarize_env_changes(_env_values(), state.env_sync):
            print(f"[PDM] {line}")
    if not state.ready:
        raise ServiceBootstrapError(
            f"Pest & Disease service did not become reachable at {settings.pdm.base_url}"
        )
    return state
