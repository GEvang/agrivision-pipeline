from __future__ import annotations

from typing import Any

from agrivision.config.settings import (
    get_project_root,
    get_runtime_settings_path,
    get_settings,
)


def get_runtime_config() -> dict[str, Any]:
    settings = get_settings()
    return {
        'project_root': str(get_project_root()),
        'runtime_settings_file': str(get_runtime_settings_path()),
        'weather_base_url': settings.weather.base_url,
        'irrigation_base_url': settings.irrigation.base_url,
        'pdm_base_url': settings.pdm.base_url,
        'weather_service_dir': settings.weather.service_dir,
        'irrigation_service_dir': settings.irrigation.service_dir,
        'pdm_service_dir': settings.pdm.service_dir,
    }
