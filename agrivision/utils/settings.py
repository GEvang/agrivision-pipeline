from __future__ import annotations

import os
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_CONFIG_PATH = _PROJECT_ROOT / "config.yaml"


DEFAULT_CONFIG: dict[str, Any] = {
    "location": {
        "name": "Neapolis, Agios Nikolaos, Crete",
        "lat": 35.2600,
        "lon": 25.6000,
    },
    "paths": {
        "data_root": "data",
        "output_root": "output",
        "images_full": "data/images_full/rgb",
        "images_resized": "data/images_resized/rgb",
        "odm_project_root": "data/odm_project_rgb",
        "odm_project_root_rgb": "data/odm_project_rgb",
        "odm_project_root_mapir": "data/odm_project_mapir",
        "ndvi_output": "output/ndvi",
        "runs_output": "output/runs",
        "images_full_mapir": "data/images_full/mapir",
        "images_resized_mapir": "data/images_resized/mapir",
    },
    "resize": {
        "max_long_edge": 3000,
    },
    "ndvi": {
        "poor_max": 0.25,
        "medium_max": 0.4,
        "grid_rows": 17,
        "grid_cols": 17,
        "mapir_profile": {
            "index_mode": "nir_green",
            "nir_band": 1,
            "green_band": 2,
            "red_band": None,
        },
        "rgb_profile": {
            "index_mode": "pseudo",
            "red_band": 1,
            "nir_band": 2,
        },
    },
    "weather": {
        "base_url": "http://127.0.0.1:8010",
        "username": "",
        "password": "",
        "openweather_api_key": "",
    },
    "irrigation": {
        "base_url": "http://127.0.0.1:8004",
        "auth": {
            "email": "",
            "password": "",
        },
        "token": "",
        "default_parcel_wkt": "POINT (35.2600 25.6000)",
        "eto": {
            "location_id": 1,
            "days_back": 1,
        },
        "timeout_seconds": 20,
        "service_dir": "OpenAgri-IrrigationManagement",
    },
    "orthophoto": {
        "odm_docker_image": "opendronemap/odm:latest",
        "orthophoto_resolution_cm": 1,
    },
}


_ENV_SECRET_OVERRIDES: tuple[tuple[tuple[str, ...], str, str], ...] = (
    (("weather", "username"), "WEATHER_USERNAME", "weather.username"),
    (("weather", "password"), "WEATHER_PASSWORD", "weather.password"),
    (("weather", "openweather_api_key"), "OPENWEATHER_API_KEY", "weather.openweather_api_key"),
    (("irrigation", "auth", "email"), "IRRIGATION_EMAIL", "irrigation.auth.email"),
    (("irrigation", "auth", "password"), "IRRIGATION_PASSWORD", "irrigation.auth.password"),
    (("irrigation", "token"), "IRRIGATION_TOKEN", "irrigation.token"),
)


@dataclass(frozen=True)
class PathsSettings:
    data_root: str
    output_root: str
    images_full: str
    images_resized: str
    odm_project_root: str
    odm_project_root_rgb: str
    odm_project_root_mapir: str
    ndvi_output: str
    runs_output: str
    images_full_mapir: str
    images_resized_mapir: str

@dataclass(frozen=True)
class OrthophotoSettings:
    odm_docker_image: str
    orthophoto_resolution_cm: int

@dataclass(frozen=True)
class WeatherSettings:
    base_url: str
    username: str
    password: str
    openweather_api_key: str


@dataclass(frozen=True)
class LocationSettings:
    name: str
    lat: float
    lon: float


@dataclass(frozen=True)
class IrrigationAuthSettings:
    email: str
    password: str


@dataclass(frozen=True)
class IrrigationEtoSettings:
    location_id: int
    days_back: int


@dataclass(frozen=True)
class IrrigationSettings:
    base_url: str
    auth: IrrigationAuthSettings
    eto: IrrigationEtoSettings
    default_parcel_wkt: str
    token: str
    timeout_seconds: int
    service_dir: str


@dataclass(frozen=True)
class NdviSettings:
    poor_max: float
    medium_max: float
    grid_rows: int
    grid_cols: int
    mapir_profile: dict[str, Any]
    rgb_profile: dict[str, Any]


@dataclass(frozen=True)
class ResizeSettings:
    max_long_edge: int


@dataclass(frozen=True)
class AppSettings:
    paths: PathsSettings
    weather: WeatherSettings
    location: LocationSettings
    irrigation: IrrigationSettings
    ndvi: NdviSettings
    resize: ResizeSettings
    orthophoto: OrthophotoSettings
    

def get_project_root() -> Path:
    """Return the repository root resolved relative to this module."""
    return _PROJECT_ROOT


def get_config_path() -> Path:
    """Return the default config path (<project_root>/config.yaml)."""
    return _CONFIG_PATH


def _deep_copy(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _deep_copy(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_deep_copy(item) for item in value]
    return value


def _deep_merge(base: dict[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    merged = _deep_copy(base)
    for key, override_value in override.items():
        base_value = merged.get(key)
        if isinstance(base_value, dict) and isinstance(override_value, Mapping):
            merged[key] = _deep_merge(base_value, override_value)
        else:
            merged[key] = _deep_copy(override_value)
    return merged


def _set_if_env_exists(config: dict[str, Any], path: tuple[str, ...], env_name: str) -> None:
    value = os.getenv(env_name)
    if value is None or value == "":
        return

    current: dict[str, Any] = config
    for key in path[:-1]:
        node = current.get(key)
        if not isinstance(node, dict):
            node = {}
            current[key] = node
        current = node

    current[path[-1]] = value


def _read_nested(config: Mapping[str, Any], path: tuple[str, ...]) -> Any:
    current: Any = config
    for key in path:
        if not isinstance(current, Mapping) or key not in current:
            return None
        current = current[key]
    return current


def _warn_if_yaml_secret_used(config: Mapping[str, Any], path: tuple[str, ...], env_name: str, label: str) -> None:
    env_value = os.getenv(env_name)
    if env_value is not None and env_value != "":
        return

    value = _read_nested(config, path)
    if value not in (None, ""):
        warnings.warn(
            f"{label} is being read from config.yaml. "
            f"Set {env_name} in .env or the environment instead.",
            UserWarning,
            stacklevel=2,
        )


def _apply_env_overrides(config: dict[str, Any]) -> dict[str, Any]:
    for path, env_name, _label in _ENV_SECRET_OVERRIDES:
        _set_if_env_exists(config, path, env_name)
    return config


def _warn_for_yaml_secrets(config: Mapping[str, Any]) -> None:
    for path, env_name, label in _ENV_SECRET_OVERRIDES:
        _warn_if_yaml_secret_used(config, path, env_name, label)


def load_raw_config(config_path: Path | None = None) -> dict[str, Any]:
    """Load raw YAML config as a dict. Missing config files return an empty mapping."""
    resolved = config_path or get_config_path()
    if not resolved.exists():
        return {}

    with resolved.open("r", encoding="utf-8") as f:
        loaded = yaml.safe_load(f) or {}

    if not isinstance(loaded, dict):
        raise ValueError(f"Config file must contain a top-level mapping: {resolved}")

    return loaded


def load_config() -> dict:
    """Return config dict with explicit precedence: defaults < YAML < environment."""
    config = _deep_merge(DEFAULT_CONFIG, load_raw_config())
    config = _apply_env_overrides(config)
    _warn_for_yaml_secrets(config)
    return config


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_str(value: Any, fallback: str = "") -> str:
    if value is None:
        return fallback
    return str(value)


def _as_int(value: Any, fallback: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _as_float(value: Any, fallback: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def get_settings() -> AppSettings:
    """Build typed settings from merged config without import-time caching."""
    cfg = load_config()

    defaults = DEFAULT_CONFIG
    paths_cfg = _as_dict(cfg.get("paths"))
    weather_cfg = _as_dict(cfg.get("weather"))
    location_cfg = _as_dict(cfg.get("location"))
    irrigation_cfg = _as_dict(cfg.get("irrigation"))
    irrigation_auth_cfg = _as_dict(irrigation_cfg.get("auth"))
    irrigation_eto_cfg = _as_dict(irrigation_cfg.get("eto"))
    ndvi_cfg = _as_dict(cfg.get("ndvi"))
    resize_cfg = _as_dict(cfg.get("resize"))
    orthophoto_cfg = _as_dict(cfg.get("orthophoto"))

    paths_defaults = _as_dict(defaults.get("paths"))
    weather_defaults = _as_dict(defaults.get("weather"))
    location_defaults = _as_dict(defaults.get("location"))
    irrigation_defaults = _as_dict(defaults.get("irrigation"))
    irrigation_auth_defaults = _as_dict(irrigation_defaults.get("auth"))
    irrigation_eto_defaults = _as_dict(irrigation_defaults.get("eto"))
    ndvi_defaults = _as_dict(defaults.get("ndvi"))
    resize_defaults = _as_dict(defaults.get("resize"))
    orthophoto_defaults = _as_dict(defaults.get("orthophoto"))

    return AppSettings(
        paths=PathsSettings(
            data_root=_as_str(paths_cfg.get("data_root"), _as_str(paths_defaults.get("data_root"))),
            output_root=_as_str(paths_cfg.get("output_root"), _as_str(paths_defaults.get("output_root"))),
            images_full=_as_str(paths_cfg.get("images_full"), _as_str(paths_defaults.get("images_full"))),
            images_resized=_as_str(paths_cfg.get("images_resized"), _as_str(paths_defaults.get("images_resized"))),
            odm_project_root=_as_str(paths_cfg.get("odm_project_root"), _as_str(paths_defaults.get("odm_project_root"))),
            odm_project_root_rgb=_as_str(
                paths_cfg.get("odm_project_root_rgb"),
                _as_str(paths_defaults.get("odm_project_root_rgb")),
            ),
            odm_project_root_mapir=_as_str(
                paths_cfg.get("odm_project_root_mapir"),
                _as_str(paths_defaults.get("odm_project_root_mapir")),
            ),
            ndvi_output=_as_str(paths_cfg.get("ndvi_output"), _as_str(paths_defaults.get("ndvi_output"))),
            runs_output=_as_str(paths_cfg.get("runs_output"), _as_str(paths_defaults.get("runs_output"))),
            images_full_mapir=_as_str(
                paths_cfg.get("images_full_mapir"),
                _as_str(paths_defaults.get("images_full_mapir")),
            ),
            images_resized_mapir=_as_str(
                paths_cfg.get("images_resized_mapir"),
                _as_str(paths_defaults.get("images_resized_mapir")),
            ),
        ),
        weather=WeatherSettings(
            base_url=_as_str(weather_cfg.get("base_url"), _as_str(weather_defaults.get("base_url"))),
            username=_as_str(weather_cfg.get("username"), _as_str(weather_defaults.get("username"))),
            password=_as_str(weather_cfg.get("password"), _as_str(weather_defaults.get("password"))),
            openweather_api_key=_as_str(
                weather_cfg.get("openweather_api_key"),
                _as_str(weather_defaults.get("openweather_api_key")),
            ),
        ),
        location=LocationSettings(
            name=_as_str(location_cfg.get("name"), _as_str(location_defaults.get("name"))),
            lat=_as_float(location_cfg.get("lat"), _as_float(location_defaults.get("lat"), 0.0)),
            lon=_as_float(location_cfg.get("lon"), _as_float(location_defaults.get("lon"), 0.0)),
        ),
        irrigation=IrrigationSettings(
            base_url=_as_str(irrigation_cfg.get("base_url"), _as_str(irrigation_defaults.get("base_url"))),
            auth=IrrigationAuthSettings(
                email=_as_str(
                    irrigation_auth_cfg.get("email"),
                    _as_str(irrigation_auth_defaults.get("email")),
                ),
                password=_as_str(
                    irrigation_auth_cfg.get("password"),
                    _as_str(irrigation_auth_defaults.get("password")),
                ),
            ),
            eto=IrrigationEtoSettings(
                location_id=_as_int(
                    irrigation_eto_cfg.get("location_id"),
                    _as_int(irrigation_eto_defaults.get("location_id"), 1),
                ),
                days_back=_as_int(
                    irrigation_eto_cfg.get("days_back"),
                    _as_int(irrigation_eto_defaults.get("days_back"), 1),
                ),
            ),
            default_parcel_wkt=_as_str(
                irrigation_cfg.get("default_parcel_wkt"),
                _as_str(irrigation_defaults.get("default_parcel_wkt")),
            ),
            token=_as_str(irrigation_cfg.get("token"), _as_str(irrigation_defaults.get("token"))),
            timeout_seconds=_as_int(irrigation_cfg.get("timeout_seconds"), _as_int(irrigation_defaults.get("timeout_seconds"), 20)),
            service_dir=_as_str(irrigation_cfg.get("service_dir"), _as_str(irrigation_defaults.get("service_dir"), "OpenAgri-IrrigationManagement")),

        ),
        ndvi=NdviSettings(
            poor_max=_as_float(ndvi_cfg.get("poor_max"), _as_float(ndvi_defaults.get("poor_max"), 0.25)),
            medium_max=_as_float(
                ndvi_cfg.get("medium_max"),
                _as_float(ndvi_defaults.get("medium_max"), 0.4),
            ),
            grid_rows=_as_int(ndvi_cfg.get("grid_rows"), _as_int(ndvi_defaults.get("grid_rows"), 17)),
            grid_cols=_as_int(ndvi_cfg.get("grid_cols"), _as_int(ndvi_defaults.get("grid_cols"), 17)),
            mapir_profile=_as_dict(ndvi_cfg.get("mapir_profile")) or _as_dict(ndvi_defaults.get("mapir_profile")),
            rgb_profile=_as_dict(ndvi_cfg.get("rgb_profile")) or _as_dict(ndvi_defaults.get("rgb_profile")),
        ),
        resize=ResizeSettings(
            max_long_edge=_as_int(
                resize_cfg.get("max_long_edge"),
                _as_int(resize_defaults.get("max_long_edge"), 3000),
            )
        ),
        orthophoto=OrthophotoSettings(
            odm_docker_image=_as_str(
                orthophoto_cfg.get("odm_docker_image"),
                _as_str(orthophoto_defaults.get("odm_docker_image")),
            ),
            orthophoto_resolution_cm=_as_int(
                orthophoto_cfg.get("orthophoto_resolution_cm"),
                _as_int(orthophoto_defaults.get("orthophoto_resolution_cm"), 1),
            ),
        ),
    )
