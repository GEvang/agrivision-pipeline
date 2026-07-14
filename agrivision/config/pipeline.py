from __future__ import annotations

from dataclasses import asdict
from typing import Any

from agrivision.config.settings import get_settings


def get_pipeline_config() -> dict[str, Any]:
    settings = get_settings()
    return {
        "paths": asdict(settings.paths),
        "vegetation_index": asdict(settings.vegetation_index),
        "orthophoto": asdict(settings.orthophoto),
        "location": asdict(settings.location),
    }
