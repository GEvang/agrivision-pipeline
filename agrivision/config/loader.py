from __future__ import annotations

from typing import Any

from .settings import get_config_path, load_config, load_raw_config

__all__ = ["get_config_path", "load_config", "load_raw_config", "load_typed_config"]


def load_typed_config() -> dict[str, Any]:
    """Compatibility-oriented typed config loader placeholder.

    The repo still exposes dataclass-based typed settings through
    ``agrivision.config.settings.get_settings``. This helper keeps the
    architecture split explicit for callers that want a stable loader module.
    """
    return load_config()
