from __future__ import annotations

from dataclasses import asdict
from typing import Any

from agrivision.config.settings import get_settings


def get_service_config() -> dict[str, Any]:
    settings = get_settings()
    return {
        "weather": asdict(settings.weather),
        "irrigation": asdict(settings.irrigation),
    }
