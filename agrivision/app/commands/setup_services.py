from __future__ import annotations

from agrivision.services.irrigation.runtime import (
    ensure_repo_and_env as ensure_irrigation_repo_and_env,
)
from agrivision.services.pdm.runtime import ensure_repo_and_env as ensure_pdm_repo_and_env
from agrivision.services.weather.client import ensure_weather_repo_and_env


def setup_services() -> tuple[object, object, object]:
    return ensure_weather_repo_and_env(), ensure_irrigation_repo_and_env(), ensure_pdm_repo_and_env()
