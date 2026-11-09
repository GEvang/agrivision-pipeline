"""Install and run the OpenAgri Weather service next to AgriVision."""

from __future__ import annotations

import os
from pathlib import Path

from agrivision.config.settings import get_settings
from agrivision.runtime.service_runtime import (
    EnvSyncResult,
    ServiceRuntimeState,
    base_env_values,
    clone_repo_if_missing,
    ensure_env_file,
    inspect_external_service_runtime,
    project_service_dir,
    reconcile_service_runtime,
    update_env_file,
)

WEATHER_REPO_URL = "https://github.com/agstack/OpenAgri-WeatherService.git"
# Last upstream commit verified with AgriVision. Bump deliberately after testing.
WEATHER_REPO_REF = "923ecb049932b4958762d0e8e8a859505995dff7"
DEFAULT_SERVICE_USERNAME = "dummy@email.com"
DEFAULT_SERVICE_PASSWORD = "StrongPass1@"



def _service_dir() -> Path:
    settings = get_settings()
    return project_service_dir(settings.weather.service_dir or "OpenAgri-WeatherService")


def weather_env_values() -> dict[str, str]:
    settings = get_settings()
    port = str(settings.weather.base_url.rsplit(":", 1)[-1])
    values = base_env_values()
    values.update(
        {
            "SOURCE_REPO": "openagri-eu/openagri-weatherservice",
            "WEATHER_SRV_PORT": port,
            "WEATHER_SRV_DATABASE_URI": "mongodb://root:root@mongodb:27017",
            "WEATHER_SRV_DATABASE_NAME": "openagridb",
            "WEATHER_SRV_MONGO_INITDB_ROOT_USERNAME": "root",
            "WEATHER_SRV_MONGO_INITDB_ROOT_PASSWORD": "root",
            "WEATHER_SRV_MONGO_INITDB_DATABASE": "openagridb",
            "WEATHER_SRV_OPENWEATHERMAP_API_KEY": settings.weather.openweather_api_key or "",
            "GATEKEEPER_SUPERUSER_USERNAME": settings.weather.username or DEFAULT_SERVICE_USERNAME,
            "GATEKEEPER_SUPERUSER_PASSWORD": settings.weather.password or DEFAULT_SERVICE_PASSWORD,
            "WEATHER_SRV_GATEKEEPER_USER": settings.weather.username or DEFAULT_SERVICE_USERNAME,
            "WEATHER_SRV_GATEKEEPER_PASSWORD": settings.weather.password or DEFAULT_SERVICE_PASSWORD,
        }
    )
    return values


def ensure_weather_repo_and_env(timeout_seconds: int = 90) -> ServiceRuntimeState:
    base_url = get_settings().weather.base_url.rstrip("/")
    health_urls = [f"{base_url}/docs", f"{base_url}/openapi.json", f"{base_url}/"]
    if os.getenv("APP_CONTAINER_PROJECT_ROOT", "").strip():
        return inspect_external_service_runtime(
            repo_dir=_service_dir(),
            readiness_urls=health_urls,
            timeout_seconds=timeout_seconds,
        )
    return reconcile_service_runtime(
        repo_dir=_service_dir(),
        repo_url=WEATHER_REPO_URL,
        repo_ref=WEATHER_REPO_REF,
        env_values=weather_env_values(),
        compose_candidates=[
            "docker-compose-x86_64.yml",
            "docker-compose-arm64.yml",
            "docker-compose.yml",
            "docker-compose.yaml",
        ],
        readiness_urls=health_urls,
        timeout_seconds=timeout_seconds,
    )


def prepare_weather_repo_and_env() -> EnvSyncResult:
    repo_dir = _service_dir()
    clone_repo_if_missing(repo_dir, WEATHER_REPO_URL, WEATHER_REPO_REF)
    env_path = ensure_env_file(repo_dir)
    return update_env_file(env_path, weather_env_values())
