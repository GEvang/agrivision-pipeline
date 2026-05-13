from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from agrivision.config.settings import get_settings
from agrivision.services.irrigation import runtime as irrigation_runtime
from agrivision.services.pdm import runtime as pdm_runtime
from agrivision.services.runtime import (
    ServiceBootstrapError,
    check_first_reachable_url,
    compose_logs,
    compose_restart,
    detect_compose_file,
    project_service_dir,
)
from agrivision.services.weather import client as weather_client


@dataclass(frozen=True)
class ServiceDescriptor:
    key: str
    name: str
    base_url: str
    repo_dir: Path
    readiness_urls: tuple[str, ...]
    ensure: Callable[..., object]
    docs_url: str


def service_descriptors() -> dict[str, ServiceDescriptor]:
    settings = get_settings()
    weather_base = settings.weather.base_url.rstrip("/")
    irrigation_base = settings.irrigation.base_url.rstrip("/")
    pdm_base = settings.pdm.base_url.rstrip("/")
    return {
        "weather": ServiceDescriptor(
            key="weather",
            name="Weather",
            base_url=weather_base,
            repo_dir=project_service_dir("OpenAgri-WeatherService"),
            readiness_urls=(f"{weather_base}/docs", f"{weather_base}/openapi.json", f"{weather_base}/"),
            ensure=weather_client.ensure_weather_repo_and_env,
            docs_url=f"{weather_base}/docs",
        ),
        "irrigation": ServiceDescriptor(
            key="irrigation",
            name="Irrigation",
            base_url=irrigation_base,
            repo_dir=project_service_dir(settings.irrigation.service_dir or "OpenAgri-IrrigationManagement"),
            readiness_urls=(
                f"{irrigation_base}/openapi.json",
                f"{irrigation_base}/docs",
                f"{irrigation_base}/api/v1/openapi.json",
            ),
            ensure=irrigation_runtime.ensure_service_available,
            docs_url=f"{irrigation_base}/docs",
        ),
        "pdm": ServiceDescriptor(
            key="pdm",
            name="PDM",
            base_url=pdm_base,
            repo_dir=project_service_dir(settings.pdm.service_dir or "OpenAgri-PestAndDiseaseManagement"),
            readiness_urls=(
                f"{pdm_base}/openapi.json",
                f"{pdm_base}/docs",
                f"{pdm_base}/health",
                f"{pdm_base}/api/v1/openapi.json",
            ),
            ensure=pdm_runtime.ensure_service_available,
            docs_url=f"{pdm_base}/docs",
        ),
    }


def service_statuses(*, include_logs: bool = False) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    for descriptor in service_descriptors().values():
        repo_exists = descriptor.repo_dir.exists()
        compose_file = None
        compose_error = ""
        logs = ""
        if repo_exists:
            try:
                compose_file = detect_compose_file(descriptor.repo_dir)
                if include_logs:
                    logs = compose_logs(compose_file, descriptor.repo_dir, tail=80)
            except ServiceBootstrapError as exc:
                compose_error = str(exc)
        reachable = check_first_reachable_url(descriptor.readiness_urls)
        state = "ok" if reachable else ("warn" if repo_exists else "missing")
        detail = "Reachable" if reachable else ("Repo exists, service not reachable" if repo_exists else "Repository not cloned")
        if compose_error:
            state = "warn"
            detail = compose_error
        items.append(
            {
                "key": descriptor.key,
                "name": descriptor.name,
                "base_url": descriptor.base_url,
                "docs_url": descriptor.docs_url,
                "repo_dir": str(descriptor.repo_dir),
                "repo_exists": repo_exists,
                "compose_file": str(compose_file) if compose_file else "",
                "state": state,
                "detail": detail,
                "readiness_urls": list(descriptor.readiness_urls),
                "logs": logs,
            }
        )
    return items


def ensure_service(key: str, *, timeout_seconds: int = 90) -> None:
    descriptor = service_descriptors()[key]
    descriptor.ensure(timeout_seconds=timeout_seconds)


def restart_service(key: str, *, timeout_seconds: int = 90) -> None:
    descriptor = service_descriptors()[key]
    descriptor.ensure(timeout_seconds=timeout_seconds)
    compose_file = detect_compose_file(descriptor.repo_dir)
    compose_restart(compose_file, descriptor.repo_dir)
    descriptor.ensure(timeout_seconds=timeout_seconds)
