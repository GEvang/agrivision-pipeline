from __future__ import annotations

from typing import Any

from agrivision.config.settings import get_project_root, get_settings


def get_runtime_config() -> dict[str, Any]:
    settings = get_settings()
    return {
        "project_root": str(get_project_root()),
        "weather_base_url": settings.weather.base_url,
        "irrigation_base_url": settings.irrigation.base_url,
        "service_dir": settings.irrigation.service_dir,
    }
