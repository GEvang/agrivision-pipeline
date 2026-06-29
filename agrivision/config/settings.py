from __future__ import annotations

import json
import os
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit, urlunsplit

import yaml

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_CONFIG_PATH = Path(os.getenv("AGRIVISION_CONFIG_PATH", str(_PROJECT_ROOT / "config.yaml")))
_RUNTIME_SETTINGS_PATH = Path(
    os.getenv("AGRIVISION_RUNTIME_SETTINGS_PATH", str(_PROJECT_ROOT / "runtime" / "settings.json"))
)
DEFAULT_SERVICE_USERNAME = "dummy@email.com"
DEFAULT_SERVICE_PASSWORD = "StrongPass1@"


def load_local_env(env_path: Path | None = None) -> None:
    resolved = env_path or (get_config_path().parent / ".env")
    if not resolved.exists():
        return
    for raw_line in resolved.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _remove_yaml_secrets(config: dict[str, Any]) -> dict[str, Any]:
    weather = config.setdefault("weather", {})
    weather["username"] = ""
    weather["password"] = ""
    weather["openweather_api_key"] = ""
    irrigation = config.setdefault("irrigation", {})
    irrigation_auth = irrigation.setdefault("auth", {})
    irrigation_auth["email"] = ""
    irrigation_auth["password"] = ""
    irrigation["token"] = ""
    pdm = config.setdefault("pdm", {})
    pdm_auth = pdm.setdefault("auth", {})
    pdm_auth["username"] = ""
    pdm_auth["password"] = ""
    pdm["token"] = ""
    return config


def _apply_local_service_defaults(config: dict[str, Any]) -> dict[str, Any]:
    weather = config.setdefault("weather", {})
    if not weather.get("username"):
        weather["username"] = DEFAULT_SERVICE_USERNAME
    if not weather.get("password"):
        weather["password"] = DEFAULT_SERVICE_PASSWORD

    irrigation = config.setdefault("irrigation", {})
    irrigation_auth = irrigation.setdefault("auth", {})
    if not irrigation_auth.get("email"):
        irrigation_auth["email"] = DEFAULT_SERVICE_USERNAME
    if not irrigation_auth.get("password"):
        irrigation_auth["password"] = DEFAULT_SERVICE_PASSWORD

    pdm = config.setdefault("pdm", {})
    pdm_auth = pdm.setdefault("auth", {})
    if not pdm_auth.get("username"):
        pdm_auth["username"] = DEFAULT_SERVICE_USERNAME
    if not pdm_auth.get("password"):
        pdm_auth["password"] = DEFAULT_SERVICE_PASSWORD
    return config


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
        "odm_project_root_thermal": "data/odm_project_thermal",
        "ndvi_output": "output/ndvi",
        "runs_output": "output/runs",
        "images_full_mapir": "data/images_full/mapir",
        "images_resized_mapir": "data/images_resized/mapir",
        "images_full_thermal": "data/images_full/thermal",
        "images_resized_thermal": "data/images_resized/thermal",
    },
    "resize": {
        "max_long_edge": 3000,
    },
    "ndvi": {
        "poor_max": 0.25,
        "medium_max": 0.4,
        "threshold_mode": "fixed",
        "calibration_percentiles": [33, 66],
        "min_cell_valid_fraction": 0.2,
        "grid_rows": 17,
        "grid_cols": 17,
        "mapir_profile": {
            "index_mode": "nir_red",
            "nir_band": 3,
            "green_band": None,
            "red_band": 1,
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
        "service_dir": "OpenAgri-WeatherService",
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
    "app": {
        "deployment_mode": "local",
        "public_url": "",
        "min_free_disk_gb": 50,
        "max_active_odm_runs": 1,
        "external_access_protection_confirmed": False,
    },
    "pdm": {
        "enabled_by_default": True,
        "base_url": "http://127.0.0.1:8006",
        "auth": {
            "username": "",
            "password": "",
        },
        "token": "",
        "timeout_seconds": 12,
        "verify_ssl": False,
        "default_crop": "grapevine",
        "default_model_key": "grapevine_powdery_mildew_risk_v1",
        "allow_per_run_override": True,
        "service_dir": "OpenAgri-PestAndDiseaseManagement",
    },
}


_ENV_SECRET_OVERRIDES: tuple[tuple[tuple[str, ...], str, str], ...] = (
    (("weather", "username"), "WEATHER_USERNAME", "weather.username"),
    (("weather", "password"), "WEATHER_PASSWORD", "weather.password"),
    (("weather", "openweather_api_key"), "OPENWEATHER_API_KEY", "weather.openweather_api_key"),
    (("irrigation", "auth", "email"), "IRRIGATION_EMAIL", "irrigation.auth.email"),
    (("irrigation", "auth", "password"), "IRRIGATION_PASSWORD", "irrigation.auth.password"),
    (("irrigation", "token"), "IRRIGATION_TOKEN", "irrigation.token"),
    (("pdm", "auth", "username"), "PDM_USERNAME", "pdm.auth.username"),
    (("pdm", "auth", "password"), "PDM_PASSWORD", "pdm.auth.password"),
    (("pdm", "token"), "PDM_TOKEN", "pdm.token"),
    (("app", "deployment_mode"), "AGRIVISION_DEPLOYMENT_MODE", "app.deployment_mode"),
    (("app", "public_url"), "AGRIVISION_PUBLIC_URL", "app.public_url"),
    (("app", "min_free_disk_gb"), "AGRIVISION_MIN_FREE_DISK_GB", "app.min_free_disk_gb"),
    (("app", "max_active_odm_runs"), "AGRIVISION_MAX_ACTIVE_ODM_RUNS", "app.max_active_odm_runs"),
    (
        ("app", "external_access_protection_confirmed"),
        "AGRIVISION_EXTERNAL_ACCESS_PROTECTION_CONFIRMED",
        "app.external_access_protection_confirmed",
    ),
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
    odm_project_root_thermal: str
    ndvi_output: str
    runs_output: str
    images_full_mapir: str
    images_resized_mapir: str
    images_full_thermal: str
    images_resized_thermal: str


@dataclass(frozen=True)
class OrthophotoSettings:
    odm_docker_image: str
    orthophoto_resolution_cm: int


@dataclass(frozen=True)
class ApplicationSettings:
    deployment_mode: str
    public_url: str
    min_free_disk_gb: int
    max_active_odm_runs: int
    external_access_protection_confirmed: bool


@dataclass(frozen=True)
class WeatherSettings:
    base_url: str
    username: str
    password: str
    openweather_api_key: str
    service_dir: str


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
class PdmAuthSettings:
    username: str
    password: str


@dataclass(frozen=True)
class PdmSettings:
    enabled_by_default: bool
    base_url: str
    auth: PdmAuthSettings
    token: str
    timeout_seconds: int
    verify_ssl: bool
    default_crop: str
    default_model_key: str
    allow_per_run_override: bool
    service_dir: str

@dataclass(frozen=True)
class NdviSettings:
    poor_max: float
    medium_max: float
    threshold_mode: str
    calibration_percentiles: list[float]
    min_cell_valid_fraction: float
    grid_rows: int
    grid_cols: int
    mapir_profile: dict[str, Any]
    rgb_profile: dict[str, Any]


@dataclass(frozen=True)
class ResizeSettings:
    max_long_edge: int


@dataclass(frozen=True)
class AppSettings:
    app: ApplicationSettings
    paths: PathsSettings
    weather: WeatherSettings
    location: LocationSettings
    irrigation: IrrigationSettings
    pdm: PdmSettings
    ndvi: NdviSettings
    resize: ResizeSettings
    orthophoto: OrthophotoSettings
    

def get_project_root() -> Path:
    """Return the active project root.

    AGRIVISION_PROJECT_ROOT always wins when explicitly set. This is used by
    the host-side service helper to operate on the real checkout through a bind
    mount while reusing the packaged AgriVision Python code.

    When AGRIVISION_CONFIG_PATH points at a config file inside a bind-mounted
    workspace (for example /workspace/config.yaml in Docker), the config file's
    parent directory becomes the runtime project root. Otherwise we fall back to
    the repository root resolved from this module.
    """
    overridden_root = os.getenv("AGRIVISION_PROJECT_ROOT", "").strip()
    if overridden_root:
        return Path(overridden_root).resolve()
    if _CONFIG_PATH.name == "config.yaml":
        return _CONFIG_PATH.resolve().parent
    return _PROJECT_ROOT


def get_config_path() -> Path:
    """Return the active config path, allowing AGRIVISION_CONFIG_PATH overrides."""
    return _CONFIG_PATH


def get_runtime_settings_path() -> Path:
    """Return the dashboard-managed runtime settings file path."""
    return _RUNTIME_SETTINGS_PATH


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


def _rewrite_loopback_urls_for_container(config: dict[str, Any]) -> dict[str, Any]:
    if not os.getenv("APP_CONTAINER_PROJECT_ROOT"):
        return config
    if os.getenv("AGRIVISION_REWRITE_LOOPBACK_URLS", "1").strip().lower() in {"0", "false", "no"}:
        return config

    for section in ("weather", "irrigation", "pdm"):
        value = config.get(section, {}).get("base_url")
        if not isinstance(value, str) or not value:
            continue
        parsed = urlsplit(value)
        if parsed.hostname not in {"127.0.0.1", "localhost"}:
            continue
        port = f":{parsed.port}" if parsed.port is not None else ""
        config[section]["base_url"] = urlunsplit(
            (parsed.scheme, f"host.docker.internal{port}", parsed.path, parsed.query, parsed.fragment)
        )
    return config


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


def load_runtime_settings(runtime_settings_path: Path | None = None) -> dict[str, Any]:
    """Load dashboard-managed runtime settings as a dict. Missing files return an empty mapping."""
    resolved = runtime_settings_path or get_runtime_settings_path()
    if not resolved.exists():
        return {}

    loaded = json.loads(resolved.read_text(encoding="utf-8") or "{}")

    if not isinstance(loaded, dict):
        raise ValueError(f"Runtime settings file must contain a top-level mapping: {resolved}")

    return loaded


def load_config() -> dict:
    """Return config dict with explicit precedence: defaults < config.yaml < runtime/settings.json < .env/environment."""
    load_local_env()
    config = _deep_merge(DEFAULT_CONFIG, load_raw_config())
    config = _deep_merge(config, load_runtime_settings())
    config = _remove_yaml_secrets(config)
    config = _apply_env_overrides(config)
    config = _apply_local_service_defaults(config)
    config = _rewrite_loopback_urls_for_container(config)
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


def _as_bool(value: Any, fallback: bool) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return fallback
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
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
    pdm_cfg = _as_dict(cfg.get("pdm"))
    pdm_auth_cfg = _as_dict(pdm_cfg.get("auth"))
    ndvi_cfg = _as_dict(cfg.get("ndvi"))
    resize_cfg = _as_dict(cfg.get("resize"))
    orthophoto_cfg = _as_dict(cfg.get("orthophoto"))
    app_cfg = _as_dict(cfg.get("app"))

    paths_defaults = _as_dict(defaults.get("paths"))
    weather_defaults = _as_dict(defaults.get("weather"))
    location_defaults = _as_dict(defaults.get("location"))
    irrigation_defaults = _as_dict(defaults.get("irrigation"))
    irrigation_auth_defaults = _as_dict(irrigation_defaults.get("auth"))
    irrigation_eto_defaults = _as_dict(irrigation_defaults.get("eto"))
    pdm_defaults = _as_dict(defaults.get("pdm"))
    pdm_auth_defaults = _as_dict(pdm_defaults.get("auth"))
    ndvi_defaults = _as_dict(defaults.get("ndvi"))
    resize_defaults = _as_dict(defaults.get("resize"))
    orthophoto_defaults = _as_dict(defaults.get("orthophoto"))
    app_defaults = _as_dict(defaults.get("app"))

    return AppSettings(
        app=ApplicationSettings(
            deployment_mode=_as_str(
                app_cfg.get("deployment_mode"),
                _as_str(app_defaults.get("deployment_mode"), "local"),
            ),
            public_url=_as_str(app_cfg.get("public_url"), _as_str(app_defaults.get("public_url"))),
            min_free_disk_gb=max(
                0,
                _as_int(app_cfg.get("min_free_disk_gb"), _as_int(app_defaults.get("min_free_disk_gb"), 50)),
            ),
            max_active_odm_runs=max(
                1,
                _as_int(
                    app_cfg.get("max_active_odm_runs"),
                    _as_int(app_defaults.get("max_active_odm_runs"), 1),
                ),
            ),
            external_access_protection_confirmed=_as_bool(
                app_cfg.get("external_access_protection_confirmed"),
                _as_bool(app_defaults.get("external_access_protection_confirmed"), False),
            ),
        ),
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
            odm_project_root_thermal=_as_str(
                paths_cfg.get("odm_project_root_thermal"),
                _as_str(paths_defaults.get("odm_project_root_thermal")),
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
            images_full_thermal=_as_str(
                paths_cfg.get("images_full_thermal"),
                _as_str(paths_defaults.get("images_full_thermal")),
            ),
            images_resized_thermal=_as_str(
                paths_cfg.get("images_resized_thermal"),
                _as_str(paths_defaults.get("images_resized_thermal")),
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
            service_dir=_as_str(weather_cfg.get("service_dir"), _as_str(weather_defaults.get("service_dir"), "OpenAgri-WeatherService")),
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
        pdm=PdmSettings(
            enabled_by_default=bool(pdm_cfg.get("enabled_by_default", pdm_defaults.get("enabled_by_default", True))),
            base_url=_as_str(pdm_cfg.get("base_url"), _as_str(pdm_defaults.get("base_url"))),
            auth=PdmAuthSettings(
                username=_as_str(pdm_auth_cfg.get("username"), _as_str(pdm_auth_defaults.get("username"))),
                password=_as_str(pdm_auth_cfg.get("password"), _as_str(pdm_auth_defaults.get("password"))),
            ),
            token=_as_str(pdm_cfg.get("token"), _as_str(pdm_defaults.get("token"))),
            timeout_seconds=_as_int(pdm_cfg.get("timeout_seconds"), _as_int(pdm_defaults.get("timeout_seconds"), 12)),
            verify_ssl=bool(pdm_cfg.get("verify_ssl", pdm_defaults.get("verify_ssl", False))),
            default_crop=_as_str(pdm_cfg.get("default_crop"), _as_str(pdm_defaults.get("default_crop"), "grapevine")),
            default_model_key=_as_str(pdm_cfg.get("default_model_key"), _as_str(pdm_defaults.get("default_model_key"), "grapevine_powdery_mildew_risk_v1")),
            allow_per_run_override=bool(pdm_cfg.get("allow_per_run_override", pdm_defaults.get("allow_per_run_override", True))),
            service_dir=_as_str(pdm_cfg.get("service_dir"), _as_str(pdm_defaults.get("service_dir"), "OpenAgri-PestAndDiseaseManagement")),
        ),
        ndvi=NdviSettings(
            poor_max=_as_float(ndvi_cfg.get("poor_max"), _as_float(ndvi_defaults.get("poor_max"), 0.25)),
            medium_max=_as_float(
                ndvi_cfg.get("medium_max"),
                _as_float(ndvi_defaults.get("medium_max"), 0.4),
            ),
            threshold_mode=_as_str(
                ndvi_cfg.get("threshold_mode"),
                _as_str(ndvi_defaults.get("threshold_mode"), "fixed"),
            ),
            calibration_percentiles=[
                _as_float(value, fallback)
                for value, fallback in zip(
                    ndvi_cfg.get(
                        "calibration_percentiles",
                        ndvi_defaults.get("calibration_percentiles", [33, 66]),
                    ),
                    [33, 66],
                )
            ],
            min_cell_valid_fraction=_as_float(
                ndvi_cfg.get("min_cell_valid_fraction"),
                _as_float(ndvi_defaults.get("min_cell_valid_fraction"), 0.2),
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
