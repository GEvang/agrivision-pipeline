from pathlib import Path
import os
import yaml
import warnings

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_CONFIG_PATH = _PROJECT_ROOT / "config.yaml"


def get_project_root() -> Path:
    return _PROJECT_ROOT


def _set_if_env_exists(config: dict, path: tuple[str, ...], env_name: str) -> None:
    value = os.getenv(env_name)
    if value is None or value == "":
        return

    current = config
    for key in path[:-1]:
        if key not in current or not isinstance(current[key], dict):
            current[key] = {}
        current = current[key]

    current[path[-1]] = value

def _apply_env_overrides(config: dict) -> dict:
    _set_if_env_exists(config, ("weather", "username"), "WEATHER_USERNAME")
    _set_if_env_exists(config, ("weather", "password"), "WEATHER_PASSWORD")
    _set_if_env_exists(config, ("weather", "openweather_api_key"), "OPENWEATHER_API_KEY")
    _set_if_env_exists(config, ("irrigation", "auth", "email"), "IRRIGATION_EMAIL")
    _set_if_env_exists(config, ("irrigation", "auth", "password"), "IRRIGATION_PASSWORD")

    _warn_if_yaml_secret_used(config, ("weather", "username"), "WEATHER_USERNAME", "weather.username")
    _warn_if_yaml_secret_used(config, ("weather", "password"), "WEATHER_PASSWORD", "weather.password")
    _warn_if_yaml_secret_used(config, ("weather", "openweather_api_key"), "OPENWEATHER_API_KEY", "weather.openweather_api_key")
    _warn_if_yaml_secret_used(config, ("irrigation", "auth", "email"), "IRRIGATION_EMAIL", "irrigation.auth.email")
    _warn_if_yaml_secret_used(config, ("irrigation", "auth", "password"), "IRRIGATION_PASSWORD", "irrigation.auth.password")

    return config


def _warn_if_yaml_secret_used(config: dict, path: tuple[str, ...], env_name: str, label: str) -> None:
    env_value = os.getenv(env_name)
    if env_value is not None and env_value != "":
        return

    current = config
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return
        current = current[key]

    if current not in (None, ""):
        warnings.warn(
            f"{label} is being read from config.yaml. "
            f"Set {env_name} in .env or the environment instead.",
            UserWarning,
            stacklevel=2,
        )


def load_config() -> dict:
    if not _CONFIG_PATH.exists():
        raise FileNotFoundError(f"Config file not found: {_CONFIG_PATH}")

    with _CONFIG_PATH.open("r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    return _apply_env_overrides(config)
