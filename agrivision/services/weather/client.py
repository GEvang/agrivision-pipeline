#!/usr/bin/env python3
"""
agrivision.services.weather.client

Client + bootstrap helpers for the OpenAgri WeatherService.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import os
from pathlib import Path
from typing import Any

import requests

from agrivision.config.settings import get_settings, load_config
from agrivision.services.runtime import (
    EnvSyncResult,
    ServiceBootstrapError,
    ServiceRuntimeState,
    base_env_values,
    clone_repo_if_missing,
    ensure_env_file,
    inspect_external_service_runtime,
    project_service_dir,
    reconcile_service_runtime,
    summarize_env_changes,
    update_env_file,
)

WEATHER_REPO_URL = "https://github.com/agstack/OpenAgri-WeatherService.git"
DEFAULT_SERVICE_USERNAME = "dummy@email.com"
DEFAULT_SERVICE_PASSWORD = "StrongPass1@"


def _get_weather_settings() -> dict[str, Any]:
    config = load_config()
    weather_cfg = config.get("weather", {})
    return {
        "base_url": weather_cfg.get("base_url", ""),
        "username": weather_cfg.get("username", ""),
        "password": weather_cfg.get("password", ""),
        "openweather_api_key": weather_cfg.get("openweather_api_key", ""),
    }


@dataclass
class CurrentWeather:
    location_name: str
    timestamp: datetime | None
    temperature: float | None
    humidity: float | None
    pressure: float | None
    wind_speed: float | None
    description: str | None
    raw: dict[str, Any]


@dataclass
class ForecastPoint:
    timestamp: datetime | None
    value: float | None
    data_type: str | None
    measurement_type: str | None
    source: str | None
    raw: dict[str, Any]


def _ts_from_unix(ts: int | float | None) -> datetime | None:
    if ts is None:
        return None
    return datetime.fromtimestamp(ts)


def _ts_from_iso(s: Any) -> datetime | None:
    if not s:
        return None
    try:
        text = str(s)
        if text.endswith("Z"):
            text = text.replace("Z", "+00:00")
        return datetime.fromisoformat(text)
    except Exception:
        return None


def _get_location_params() -> dict[str, Any]:
    config = load_config()
    location_cfg = config.get("location", {})
    return {
        "lat": float(location_cfg.get("lat", 0.0)),
        "lon": float(location_cfg.get("lon", 0.0)),
        "location_name": location_cfg.get("name", "Unknown location"),
    }


def _service_dir() -> Path:
    settings = get_settings()
    return project_service_dir(settings.weather.service_dir or "OpenAgri-WeatherService")


def _weather_env_values() -> dict[str, str]:
    settings = get_settings()
    port = str(settings.weather.base_url.rsplit(":", 1)[-1])
    values = base_env_values()
    values.update(
        {
            "SOURCE_REPO": "openagri-eu/openagri-weatherservice",
            "WEATHER_SRV_PORT": port,
            "WEATHER_SRV_DATABASE_URI": "mongodb://root:root@mongodb:27017",
            "WEATHER_SRV_DATABASE_NAME": "openagridb",
            "WEATHER_SRV_MONGO_INITDB_ROOT_USERNAME": "root",
            "WEATHER_SRV_MONGO_INITDB_ROOT_PASSWORD": "root",
            "WEATHER_SRV_MONGO_INITDB_DATABASE": "openagridb",
            "WEATHER_SRV_OPENWEATHERMAP_API_KEY": settings.weather.openweather_api_key or "",
            "GATEKEEPER_SUPERUSER_USERNAME": settings.weather.username or DEFAULT_SERVICE_USERNAME,
            "GATEKEEPER_SUPERUSER_PASSWORD": settings.weather.password or DEFAULT_SERVICE_PASSWORD,
            "WEATHER_SRV_GATEKEEPER_USER": settings.weather.username or DEFAULT_SERVICE_USERNAME,
            "WEATHER_SRV_GATEKEEPER_PASSWORD": settings.weather.password or DEFAULT_SERVICE_PASSWORD,
        }
    )
    return values


def ensure_weather_repo_and_env(timeout_seconds: int = 90) -> ServiceRuntimeState:
    base_url = _get_weather_settings()["base_url"].rstrip("/")
    health_urls = [f"{base_url}/docs", f"{base_url}/openapi.json", f"{base_url}/"]
    if os.getenv("APP_CONTAINER_PROJECT_ROOT", "").strip():
        return inspect_external_service_runtime(
            repo_dir=_service_dir(),
            readiness_urls=health_urls,
            timeout_seconds=timeout_seconds,
        )
    return reconcile_service_runtime(
        repo_dir=_service_dir(),
        repo_url=WEATHER_REPO_URL,
        env_values=_weather_env_values(),
        compose_candidates=[
            "docker-compose-x86_64.yml",
            "docker-compose-arm64.yml",
            "docker-compose.yml",
            "docker-compose.yaml",
        ],
        readiness_urls=health_urls,
        timeout_seconds=timeout_seconds,
    )


def prepare_weather_repo_and_env() -> EnvSyncResult:
    repo_dir = _service_dir()
    clone_repo_if_missing(repo_dir, WEATHER_REPO_URL)
    env_path = ensure_env_file(repo_dir)
    return update_env_file(env_path, _weather_env_values())


def _validate_weather_runtime(token: str) -> None:
    location = _get_location_params()
    base_url = str(_get_weather_settings()["base_url"]).rstrip("/")
    response = requests.get(
        f"{base_url}/api/data/weather/",
        params={"lat": location["lat"], "lon": location["lon"]},
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    if response.status_code >= 400:
        detail = response.text.strip() or response.reason
        raise ServiceBootstrapError(
            "Weather service data endpoint is reachable but unhealthy. "
            f"GET /api/data/weather/ returned HTTP {response.status_code}: {detail}"
        )


def _ensure_weather_service_available(timeout_seconds: int = 90) -> None:
    state = ensure_weather_repo_and_env(timeout_seconds=timeout_seconds)
    if state.env_sync.changed:
        for line in summarize_env_changes(_weather_env_values(), state.env_sync):
            print(f"[Weather] {line}")


def _require_weather_credentials() -> None:
    resolved = _get_weather_settings()
    if not resolved["username"] or not resolved["password"]:
        raise RuntimeError(
            "Missing weather credentials. Set WEATHER_USERNAME and WEATHER_PASSWORD in .env or the environment."
        )


def _require_openweather_key() -> None:
    if not _get_weather_settings()["openweather_api_key"]:
        raise RuntimeError(
            "Missing weather.openweather_api_key. Set OPENWEATHER_API_KEY in .env or the environment."
        )


def get_token() -> str:
    resolved = _get_weather_settings()
    base_url = str(resolved["base_url"]).rstrip("/")
    _require_weather_credentials()
    _ensure_weather_service_available()
    url = f"{base_url}/api/v1/auth/token"
    data = {
        "grant_type": "password",
        "username": resolved["username"],
        "password": resolved["password"],
    }
    resp = requests.post(
        url,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=10,
    )
    resp.raise_for_status()
    payload = resp.json()
    token = payload.get("jwt_token") or payload.get("access_token") or ""
    if not token:
        raise RuntimeError("Weather auth response did not include jwt_token/access_token.")
    return token


def _authorized_get(
    endpoint: str,
    *,
    token: str | None = None,
    params: dict[str, Any] | None = None,
    timeout: int = 15,
) -> dict[str, Any] | list[Any]:
    base_url = str(_get_weather_settings()["base_url"]).rstrip("/")
    _ensure_weather_service_available()
    auth_token = token or get_token()
    headers = {"Authorization": f"Bearer {auth_token}"}
    url = f"{base_url}{endpoint}"
    resp = requests.get(url, params=params or {}, headers=headers, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def _authorized_post(
    endpoint: str,
    *,
    payload: dict[str, Any],
    token: str | None = None,
    timeout: int = 20,
) -> dict[str, Any] | list[Any]:
    base_url = str(_get_weather_settings()["base_url"]).rstrip("/")
    _ensure_weather_service_available()
    auth_token = token or get_token()
    headers = {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}
    url = f"{base_url}{endpoint}"
    resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def _unwrap_payload(payload: dict[str, Any] | list[Any]) -> dict[str, Any] | list[Any]:
    if isinstance(payload, dict):
        return payload.get("data", payload.get("results", payload))
    return payload


def _coerce_list_payload(payload: dict[str, Any] | list[Any]) -> list[Any]:
    items = _unwrap_payload(payload)
    return items if isinstance(items, list) else []


def fetch_current_weather(token: str | None = None) -> CurrentWeather:
    _require_openweather_key()
    location = _get_location_params()
    payload = _authorized_get(
        "/api/data/weather",
        token=token,
        params={"lat": location["lat"], "lon": location["lon"]},
        timeout=10,
    )
    data = _unwrap_payload(payload)
    if not isinstance(data, dict):
        data = {}
    ts = _ts_from_unix(data.get("dt")) or _ts_from_iso(data.get("timestamp"))
    main = data.get("main", {}) if isinstance(data.get("main"), dict) else {}
    temp = data.get("temperature", main.get("temp"))
    humidity = data.get("humidity", main.get("humidity"))
    pressure = data.get("pressure", main.get("pressure"))
    wind = data.get("wind", {}) if isinstance(data.get("wind"), dict) else {}
    wind_speed = data.get("wind_speed", wind.get("speed"))
    weather_list = data.get("weather", [])
    description = data.get("conditions") or data.get("description")
    if description is None and isinstance(weather_list, list) and weather_list:
        first = weather_list[0]
        if isinstance(first, dict):
            description = first.get("description")
    return CurrentWeather(
        location_name=location["location_name"],
        timestamp=ts,
        temperature=temp,
        humidity=humidity,
        pressure=pressure,
        wind_speed=wind_speed,
        description=description,
        raw=data,
    )


def fetch_forecast5(token: str | None = None) -> list[ForecastPoint]:
    _require_openweather_key()
    location = _get_location_params()
    payload = _authorized_get(
        "/api/data/forecast5",
        token=token,
        params={"lat": location["lat"], "lon": location["lon"]},
        timeout=15,
    )
    items = _coerce_list_payload(payload)
    points: list[ForecastPoint] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        ts_raw = item.get("timestamp") or item.get("time") or item.get("ts")
        ts = _ts_from_iso(ts_raw)
        raw_val = item.get("value")
        try:
            value = float(raw_val) if raw_val is not None else None
        except (TypeError, ValueError):
            value = None
        points.append(
            ForecastPoint(
                timestamp=ts,
                value=value,
                data_type=item.get("data_type"),
                measurement_type=item.get("measurement_type"),
                source=item.get("source"),
                raw=item,
            )
        )
    return points


def fetch_forecast5_jsonld(token: str | None = None) -> dict[str, Any]:
    _require_openweather_key()
    location = _get_location_params()
    payload = _authorized_get(
        "/api/linkeddata/forecast5",
        token=token,
        params={"lat": location["lat"], "lon": location["lon"]},
        timeout=15,
    )
    return payload if isinstance(payload, dict) else {"data": payload}


def fetch_thi(token: str | None = None) -> dict[str, Any]:
    _require_openweather_key()
    location = _get_location_params()
    payload = _authorized_get(
        "/api/data/thi",
        token=token,
        params={"lat": location["lat"], "lon": location["lon"]},
        timeout=15,
    )
    return payload if isinstance(payload, dict) else {"data": payload}


def fetch_thi_jsonld(token: str | None = None) -> dict[str, Any]:
    _require_openweather_key()
    location = _get_location_params()
    payload = _authorized_get(
        "/api/linkeddata/thi",
        token=token,
        params={"lat": location["lat"], "lon": location["lon"]},
        timeout=15,
    )
    return payload if isinstance(payload, dict) else {"data": payload}


def fetch_uav_flight_forecast5(
    uav_model: str,
    status_filter: str | None = None,
    token: str | None = None,
) -> dict[str, Any]:
    _require_openweather_key()
    location = _get_location_params()
    params: dict[str, Any] = {"lat": location["lat"], "lon": location["lon"]}
    endpoint = f"/api/data/flight_forecast5/{uav_model}"
    if status_filter:
        endpoint = "/api/data/flight_forecast5"
        params["uavmodels"] = uav_model
        params["status_filter"] = status_filter
    payload = _authorized_get(endpoint, token=token, params=params, timeout=15)
    return payload if isinstance(payload, dict) else {"data": payload}


def fetch_spray_forecast(token: str | None = None) -> dict[str, Any]:
    _require_openweather_key()
    location = _get_location_params()
    payload = _authorized_get(
        "/api/data/spray_forecast",
        token=token,
        params={"lat": location["lat"], "lon": location["lon"]},
        timeout=15,
    )
    return payload if isinstance(payload, dict) else {"data": payload}


def fetch_spray_forecast_jsonld(token: str | None = None) -> dict[str, Any]:
    _require_openweather_key()
    location = _get_location_params()
    payload = _authorized_get(
        "/api/linkeddata/spray_forecast",
        token=token,
        params={"lat": location["lat"], "lon": location["lon"]},
        timeout=15,
    )
    return payload if isinstance(payload, dict) else {"data": payload}


def fetch_history_daily(
    start_date: str,
    end_date: str,
    token: str | None = None,
) -> dict[str, Any]:
    _require_openweather_key()
    location = _get_location_params()
    payload = _authorized_post(
        "/api/v1/history/daily",
        token=token,
        payload={
            "lat": location["lat"],
            "lon": location["lon"],
            "start": start_date,
            "end": end_date,
            # The Weather Service daily-history endpoint expects a request body shaped like
            # the public README example, including a variables array and radius_km.
            # Omitting them can yield HTTP 422 depending on the deployed schema.
            "variables": [
                "temperature_2m_max",
                "temperature_2m_min",
                "precipitation_sum",
            ],
            "radius_km": 10,
        },
        timeout=20,
    )
    return payload if isinstance(payload, dict) else {"data": payload}


def fetch_history_hourly(
    start_date: str,
    end_date: str,
    token: str | None = None,
) -> dict[str, Any]:
    _require_openweather_key()
    location = _get_location_params()
    payload = _authorized_post(
        "/api/v1/history/hourly",
        token=token,
        payload={
            "lat": location["lat"],
            "lon": location["lon"],
            "start": start_date,
            "end": end_date,
            "variables": [
                "temperature_2m",
                "relative_humidity_2m",
                "precipitation",
            ],
            "radius_km": 10,
        },
        timeout=20,
    )
    return payload if isinstance(payload, dict) else {"data": payload}


def _forecast_points_preview(
    points: list[ForecastPoint], limit: int = 8
) -> list[dict[str, Any]]:
    return [
        {
            "timestamp": point.timestamp.isoformat() if point.timestamp else None,
            "value": point.value,
            "data_type": point.data_type,
            "measurement_type": point.measurement_type,
            "source": point.source,
        }
        for point in points[:limit]
    ]


def collect_weather_summary(
    uav_model: str = "dji_phantom4",
    status_filter: str | None = None,
    history_start_date: str | None = None,
    history_end_date: str | None = None,
) -> dict[str, Any]:
    notes: list[str] = []
    location = _get_location_params()
    now = datetime.now(UTC)
    if history_start_date is None or history_end_date is None:
        history_end_date = now.date().isoformat()
        history_start_date = (now.date() - timedelta(days=3)).isoformat()

    summary: dict[str, Any] = {
        "enabled": True,
        "location_name": location["location_name"],
        "current_weather": {},
        "forecast5_points": [],
        "forecast5_jsonld": {},
        "thi": {},
        "thi_jsonld": {},
        "uav_flight_forecast": {},
        "spray_forecast": {},
        "spray_forecast_jsonld": {},
        "historical_daily": {},
        "historical_hourly": {},
        "notes": notes,
        "uav_model": uav_model,
        "status_filter": status_filter,
        "history_start_date": history_start_date,
        "history_end_date": history_end_date,
    }

    try:
        _require_openweather_key()
        token = get_token()
        _validate_weather_runtime(token)
    except Exception as exc:
        notes.append(f"Weather authentication/runtime validation failed: {exc}")
        summary["enabled"] = False
        return summary

    try:
        current = fetch_current_weather(token=token)
        summary["current_weather"] = {
            "location_name": current.location_name,
            "timestamp": current.timestamp.isoformat() if current.timestamp else None,
            "temperature": current.temperature,
            "humidity": current.humidity,
            "pressure": current.pressure,
            "wind_speed": current.wind_speed,
            "description": current.description,
            "raw": current.raw,
        }
    except Exception as exc:
        notes.append(f"Current weather fetch failed: {exc}")

    try:
        forecast_points = fetch_forecast5(token=token)
        summary["forecast5_points"] = _forecast_points_preview(forecast_points)
    except Exception as exc:
        notes.append(f"Forecast5 fetch failed: {exc}")

    try:
        summary["forecast5_jsonld"] = fetch_forecast5_jsonld(token=token)
    except Exception as exc:
        notes.append(f"Forecast5 JSON-LD fetch failed: {exc}")

    try:
        summary["thi"] = fetch_thi(token=token)
    except Exception:
        pass

    try:
        summary["thi_jsonld"] = fetch_thi_jsonld(token=token)
    except Exception:
        pass

    try:
        summary["uav_flight_forecast"] = fetch_uav_flight_forecast5(
            uav_model=uav_model,
            status_filter=status_filter,
            token=token,
        )
    except Exception:
        pass

    try:
        summary["spray_forecast"] = fetch_spray_forecast(token=token)
    except Exception:
        pass

    try:
        summary["spray_forecast_jsonld"] = fetch_spray_forecast_jsonld(token=token)
    except Exception:
        pass

    try:
        summary["historical_daily"] = fetch_history_daily(
            history_start_date,
            history_end_date,
            token=token,
        )
    except Exception:
        pass

    try:
        summary["historical_hourly"] = fetch_history_hourly(
            history_start_date,
            history_end_date,
            token=token,
        )
    except Exception:
        pass

    return summary


if __name__ == "__main__":
    try:
        cw = fetch_current_weather()
        print(cw.raw)
    except Exception as exc:
        print(f"Weather client check failed: {exc}")
