#!/usr/bin/env python3
"""
agrivision.services.weather.client

Client for the OpenAgri WeatherService.

Uses settings from config.yaml:

weather:
  base_url: "http://127.0.0.1:8010"
  username: "root"
  password: "root"
  openweather_api_key: "..."

Provides simple functions to fetch:
  - auth token
  - current weather
  - 5-day forecast
  - 5-day forecast JSON-LD (OCSM)
  - THI and THI JSON-LD
  - UAV flight forecasts
  - spray condition forecasts
  - historical daily/hourly values

Self-healing runtime behavior:
  - clone OpenAgri-WeatherService if missing
  - create/update its .env from env.example
  - inject required Docker Compose env values, including the OpenWeather key
  - start the stack with docker compose when the service is unreachable
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from agrivision.config.settings import get_project_root, load_config
from agrivision.services.runtime import (
    clone_repo_if_missing,
    compose_up,
    ensure_env_file,
    find_existing_file,
    parse_port_from_base_url,
    upsert_env_values,
    wait_for_http,
)

WEATHER_REPO_URL = "https://github.com/agstack/OpenAgri-WeatherService.git"
WEATHER_COMPOSE_CANDIDATES = ["docker-compose-x86_64.yml", "docker-compose-arm64.yml"]
WEATHER_ENV_TEMPLATES = ["env.example", ".env.example"]


@dataclass
class CurrentWeather:
    location_name: str
    timestamp: datetime | None
    temperature: float | None
    humidity: float | None
    pressure: float | None
    wind_speed: float | None
    description: str | None
    raw: Dict[str, Any]


@dataclass
class ForecastPoint:
    """Single forecast point from /api/data/forecast5."""

    timestamp: datetime | None
    value: float | None
    data_type: str | None
    measurement_type: str | None
    source: str | None
    raw: Dict[str, Any]


def _get_weather_settings() -> dict[str, Any]:
    config = load_config()
    weather_cfg = config.get("weather", {}) or {}
    return {
        "base_url": str(weather_cfg.get("base_url", "") or ""),
        "username": str(weather_cfg.get("username") or os.getenv("WEATHER_USERNAME") or ""),
        "password": str(weather_cfg.get("password") or os.getenv("WEATHER_PASSWORD") or ""),
        "openweather_api_key": str(weather_cfg.get("openweather_api_key") or os.getenv("WEATHER_SRV_OPENWEATHERMAP_API_KEY") or ""),
        "service_dir": str(weather_cfg.get("service_dir", "OpenAgri-WeatherService") or "OpenAgri-WeatherService"),
    }


def _get_location_params() -> dict[str, Any]:
    config = load_config()
    location_cfg = config.get("location", {}) or {}
    return {
        "lat": float(location_cfg.get("lat", 0.0) or 0.0),
        "lon": float(location_cfg.get("lon", 0.0) or 0.0),
        "location_name": str(location_cfg.get("name", "Unknown location") or "Unknown location"),
    }


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


def _weather_service_dir() -> Path:
    settings = _get_weather_settings()
    return get_project_root() / str(settings["service_dir"])


def _weather_runtime_url(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/docs"


def _weather_env_values() -> dict[str, str]:
    settings = _get_weather_settings()
    base_url = str(settings["base_url"])
    port = parse_port_from_base_url(base_url, 8010)
    values = {
        "TAG": "latest",
        "DOCKER_REGISTRY": "ghcr.io",
        "SOURCE_REPO": "openagri-eu/openagri-weatherservice",
        "WEATHER_SRV_PORT": str(port),
        "WEATHER_SRV_HOSTNAME": "weathersrv",
        "WEATHER_SRV_DATABASE_URI": "mongodb://root:root@mongodb:27017",
        "WEATHER_SRV_DATABASE_NAME": "openagridb",
        "WEATHER_SRV_MONGO_INITDB_ROOT_USERNAME": "root",
        "WEATHER_SRV_MONGO_INITDB_ROOT_PASSWORD": "root",
        "WEATHER_SRV_MONGO_INITDB_DATABASE": "openagridb",
        "WEATHER_SRV_EXTRA_ALLOWED_HOSTS": "127.0.0.1,localhost",
    }
    api_key = str(settings.get("openweather_api_key", "") or "").strip()
    if api_key:
        values["WEATHER_SRV_OPENWEATHERMAP_API_KEY"] = api_key
    return values


def _ensure_weather_repo_and_env() -> tuple[Path, Path]:
    repo_dir = _weather_service_dir()
    clone_repo_if_missing(repo_dir, WEATHER_REPO_URL)
    env_path = ensure_env_file(repo_dir, WEATHER_ENV_TEMPLATES)
    upsert_env_values(env_path, _weather_env_values())
    compose_file = find_existing_file(repo_dir, WEATHER_COMPOSE_CANDIDATES)
    if compose_file is None:
        raise FileNotFoundError(
            f"No WeatherService compose file found in {repo_dir}. "
            f"Expected one of: {', '.join(WEATHER_COMPOSE_CANDIDATES)}"
        )
    return repo_dir, compose_file


def _start_weather_service_if_needed(base_url: str) -> None:
    if wait_for_http(_weather_runtime_url(base_url), seconds=1, interval=0.2):
        return

    repo_dir, compose_file = _ensure_weather_repo_and_env()
    print(f"[Weather] Service not reachable. Starting stack from {compose_file} ...")
    compose_up(repo_dir, compose_file, force_recreate=True)
    if not wait_for_http(_weather_runtime_url(base_url), seconds=90, interval=2.0):
        raise RuntimeError(
            "WeatherService did not become reachable after docker compose up. "
            "Check docker ps and the WeatherService container logs."
        )


def get_token() -> str:
    resolved = _get_weather_settings()
    base_url = str(resolved["base_url"])
    username = str(resolved["username"])
    password = str(resolved["password"])

    _start_weather_service_if_needed(base_url)

    url = f"{base_url.rstrip('/')}/api/v1/auth/token"
    data = {
        "grant_type": "password",
        "username": username,
        "password": password,
    }

    resp = requests.post(
        url,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=10,
    )
    resp.raise_for_status()
    payload = resp.json()
    return str(payload.get("jwt_token") or payload.get("access_token") or payload["token"])


def _authorized_get(
    endpoint: str,
    *,
    token: str | None = None,
    params: Dict[str, Any] | None = None,
    timeout: int = 15,
) -> Dict[str, Any] | List[Any]:
    resolved = _get_weather_settings()
    base_url = str(resolved["base_url"])
    _start_weather_service_if_needed(base_url)

    auth_token = token or get_token()
    headers = {"Authorization": f"Bearer {auth_token}"}
    url = f"{base_url.rstrip('/')}{endpoint}"

    resp = requests.get(url, params=params or {}, headers=headers, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def _authorized_post(
    endpoint: str,
    *,
    payload: Dict[str, Any],
    token: str | None = None,
    timeout: int = 20,
) -> Dict[str, Any] | List[Any]:
    resolved = _get_weather_settings()
    base_url = str(resolved["base_url"])
    _start_weather_service_if_needed(base_url)

    auth_token = token or get_token()
    headers = {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json",
    }
    url = f"{base_url.rstrip('/')}{endpoint}"

    resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def _unwrap_payload(payload: Dict[str, Any] | List[Any]) -> Dict[str, Any] | List[Any]:
    if isinstance(payload, dict):
        return payload.get("data", payload.get("results", payload))
    return payload


def _coerce_list_payload(payload: Dict[str, Any] | List[Any]) -> List[Any]:
    items = _unwrap_payload(payload)
    return items if isinstance(items, list) else []


def fetch_current_weather(token: str | None = None) -> CurrentWeather:
    location = _get_location_params()
    payload = _authorized_get(
        "/api/data/weather/",
        token=token,
        params={"lat": location["lat"], "lon": location["lon"]},
        timeout=15,
    )
    data = _unwrap_payload(payload)
    if not isinstance(data, dict):
        data = {}

    ts = _ts_from_unix(data.get("dt"))
    main = data.get("main", {}) if isinstance(data.get("main"), dict) else {}
    wind = data.get("wind", {}) if isinstance(data.get("wind"), dict) else {}
    weather_list = data.get("weather", []) if isinstance(data.get("weather"), list) else []

    description = None
    if weather_list:
        first = weather_list[0]
        if isinstance(first, dict):
            description = first.get("description")

    return CurrentWeather(
        location_name=location["location_name"],
        timestamp=ts,
        temperature=main.get("temp"),
        humidity=main.get("humidity"),
        pressure=main.get("pressure"),
        wind_speed=wind.get("speed"),
        description=description,
        raw=data,
    )


def fetch_forecast5(token: Optional[str] = None) -> List[ForecastPoint]:
    location = _get_location_params()
    payload = _authorized_get(
        "/api/data/forecast5",
        token=token,
        params={"lat": location["lat"], "lon": location["lon"]},
        timeout=15,
    )
    items = _coerce_list_payload(payload)

    points: List[ForecastPoint] = []
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


def fetch_forecast5_jsonld(token: Optional[str] = None) -> Dict[str, Any]:
    location = _get_location_params()
    payload = _authorized_get(
        "/api/linkeddata/forecast5",
        token=token,
        params={"lat": location["lat"], "lon": location["lon"]},
        timeout=15,
    )
    return payload if isinstance(payload, dict) else {"data": payload}


def fetch_thi(token: Optional[str] = None) -> Dict[str, Any]:
    location = _get_location_params()
    payload = _authorized_get(
        "/api/data/thi",
        token=token,
        params={"lat": location["lat"], "lon": location["lon"]},
        timeout=15,
    )
    return payload if isinstance(payload, dict) else {"data": payload}


def fetch_thi_jsonld(token: Optional[str] = None) -> Dict[str, Any]:
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
    token: Optional[str] = None,
) -> Dict[str, Any]:
    location = _get_location_params()
    params: Dict[str, Any] = {"lat": location["lat"], "lon": location["lon"]}
    endpoint = f"/api/data/flight_forecast5/{uav_model}"
    if status_filter:
        endpoint = "/api/data/flight_forecast5"
        params["uavmodels"] = uav_model
        params["status_filter"] = status_filter
    payload = _authorized_get(endpoint, token=token, params=params, timeout=15)
    return payload if isinstance(payload, dict) else {"data": payload}


def fetch_spray_forecast(token: Optional[str] = None) -> Dict[str, Any]:
    location = _get_location_params()
    payload = _authorized_get(
        "/api/data/spray_forecast",
        token=token,
        params={"lat": location["lat"], "lon": location["lon"]},
        timeout=15,
    )
    return payload if isinstance(payload, dict) else {"data": payload}


def fetch_spray_forecast_jsonld(token: Optional[str] = None) -> Dict[str, Any]:
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
    token: Optional[str] = None,
) -> Dict[str, Any]:
    location = _get_location_params()
    payload = _authorized_post(
        "/api/v1/history/daily",
        token=token,
        payload={
            "lat": location["lat"],
            "lon": location["lon"],
            "start": start_date,
            "end": end_date,
        },
        timeout=20,
    )
    return payload if isinstance(payload, dict) else {"data": payload}


def fetch_history_hourly(
    start_date: str,
    end_date: str,
    token: Optional[str] = None,
) -> Dict[str, Any]:
    location = _get_location_params()
    payload = _authorized_post(
        "/api/v1/history/hourly",
        token=token,
        payload={
            "lat": location["lat"],
            "lon": location["lon"],
            "start": start_date,
            "end": end_date,
        },
        timeout=20,
    )
    return payload if isinstance(payload, dict) else {"data": payload}


def _forecast_points_preview(points: List[ForecastPoint], limit: int = 8) -> List[Dict[str, Any]]:
    preview: List[Dict[str, Any]] = []
    for point in points[:limit]:
        preview.append(
            {
                "timestamp": point.timestamp.isoformat() if point.timestamp else None,
                "value": point.value,
                "data_type": point.data_type,
                "measurement_type": point.measurement_type,
                "source": point.source,
            }
        )
    return preview


def collect_weather_summary(
    uav_model: str = "dji_phantom4",
    status_filter: str | None = None,
    history_start_date: str | None = None,
    history_end_date: str | None = None,
) -> Dict[str, Any]:
    notes: List[str] = []
    location = _get_location_params()
    now = datetime.now(UTC)

    if history_start_date is None or history_end_date is None:
        history_end_date = now.date().isoformat()
        history_start_date = (now.date() - timedelta(days=3)).isoformat()

    summary: Dict[str, Any] = {
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
        token = get_token()
    except Exception as exc:
        notes.append(f"Weather authentication failed: {exc}")
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
    except Exception as exc:
        notes.append(f"THI fetch failed: {exc}")

    try:
        summary["thi_jsonld"] = fetch_thi_jsonld(token=token)
    except Exception as exc:
        notes.append(f"THI JSON-LD fetch failed: {exc}")

    try:
        summary["uav_flight_forecast"] = fetch_uav_flight_forecast5(
            uav_model=uav_model,
            status_filter=status_filter,
            token=token,
        )
    except Exception as exc:
        notes.append(f"UAV flight forecast fetch failed: {exc}")

    try:
        summary["spray_forecast"] = fetch_spray_forecast(token=token)
    except Exception as exc:
        notes.append(f"Spray forecast fetch failed: {exc}")

    try:
        summary["spray_forecast_jsonld"] = fetch_spray_forecast_jsonld(token=token)
    except Exception as exc:
        notes.append(f"Spray forecast JSON-LD fetch failed: {exc}")

    try:
        summary["historical_daily"] = fetch_history_daily(
            start_date=history_start_date,
            end_date=history_end_date,
            token=token,
        )
    except Exception as exc:
        notes.append(f"Historical daily weather fetch failed: {exc}")

    try:
        summary["historical_hourly"] = fetch_history_hourly(
            start_date=history_start_date,
            end_date=history_end_date,
            token=token,
        )
    except Exception as exc:
        notes.append(f"Historical hourly weather fetch failed: {exc}")

    return summary


def _format_current_weather(cw: CurrentWeather) -> str:
    ts_str = cw.timestamp.strftime("%Y-%m-%d %H:%M") if cw.timestamp else "N/A"
    return (
        f"Location   : {cw.location_name}\n"
        f"Time       : {ts_str}\n"
        f"Temp       : {cw.temperature} °C\n"
        f"Humidity   : {cw.humidity} %\n"
        f"Pressure   : {cw.pressure} hPa\n"
        f"Wind speed : {cw.wind_speed} m/s\n"
        f"Condition  : {cw.description}\n"
    )


if __name__ == "__main__":
    cw = fetch_current_weather()
    print(_format_current_weather(cw))
