#!/usr/bin/env python3
"""
agrivision.weather.client

Client for the OpenAgri WeatherService.

Uses settings from config.yaml:

weather:
  base_url: "http://127.0.0.1:8010"
  username: "root"
  password: "root"

Provides simple functions to fetch:
  - auth token
  - current weather
  - 5-day forecast (new)

The WeatherService itself may use OpenWeather and/or other sources internally.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional
import subprocess
import time

import requests

from agrivision.utils.settings import get_project_root, load_config


CONFIG = load_config()
PROJECT_ROOT = get_project_root()

WEATHER_CFG = CONFIG["weather"]
BASE_URL: str = WEATHER_CFG.get("base_url", "http://127.0.0.1:8010")
USERNAME: str = WEATHER_CFG.get("username", "root")
PASSWORD: str = WEATHER_CFG.get("password", "root")

LOCATION_CFG = CONFIG["location"]
LAT: float = float(LOCATION_CFG["lat"])
LON: float = float(LOCATION_CFG["lon"])
LOCATION_NAME: str = LOCATION_CFG.get("name", "Unknown location")


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

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
    """
    Single forecast point from /api/data/forecast5.

    The WeatherService returns a list of items. The exact schema may evolve,
    so we keep this structure flexible and also store the raw dict.
    """
    timestamp: datetime | None
    value: float | None
    data_type: str | None
    measurement_type: str | None
    source: str | None
    raw: Dict[str, Any]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ts_from_unix(ts: int | float | None) -> datetime | None:
    if ts is None:
        return None
    return datetime.fromtimestamp(ts)


def _ts_from_iso(s: Any) -> datetime | None:
    """
    Best-effort conversion of an ISO 8601 timestamp or None.
    Handles 'Z' suffix by converting to '+00:00'.
    """
    if not s:
        return None
    try:
        text = str(s)
        if text.endswith("Z"):
            text = text.replace("Z", "+00:00")
        return datetime.fromisoformat(text)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# API calls
# ---------------------------------------------------------------------------

def get_token() -> str:
    """
    Get a JWT token from the OpenAgri WeatherService.

    Endpoint:
        POST /api/v1/auth/token
    """
    url = f"{BASE_URL}/api/v1/auth/token"
    data = {
        "grant_type": "",
        "username": USERNAME,
        "password": PASSWORD,
        "scope": "",
        "client_id": "",
        "client_secret": "",
    }

    resp = requests.post(
        url,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=10,
    )
    resp.raise_for_status()
    payload = resp.json()
    return payload["jwt_token"]


def _start_weather_service_if_needed() -> None:
    """
    Check if the WeatherService is reachable; if not, try to start it via
    `docker compose` in the OpenAgri-WeatherService folder.
    """
    # Quick connectivity check
    try:
        ping_url = f"{BASE_URL}/"
        requests.get(ping_url, timeout=2)
        return  # service is reachable, nothing to do
    except requests.RequestException:
        pass  # not reachable → try to start it

    svc_dir = PROJECT_ROOT / "OpenAgri-WeatherService"
    if not svc_dir.exists():
        print(f"[Weather] OpenAgri-WeatherService folder not found at {svc_dir}, cannot auto-start.")
        return

    print(f"[Weather] Service not reachable, trying to start via docker compose in {svc_dir}...")
    try:
        subprocess.run(
            ["docker", "compose", "-f", "docker-compose-x86_64.yml", "up", "-d"],
            cwd=str(svc_dir),
            check=False,
        )
        # give it a few seconds to come up
        time.sleep(5)
    except Exception as e:
        print(f"[Weather] Failed to start WeatherService: {e}")


def fetch_current_weather(token: str | None = None) -> CurrentWeather:
    """
    Fetch current weather from the OpenAgri WeatherService.

    Endpoint:
        GET /api/data/weather?lat={lat}&lon={lon}
    """

    # Ensure service is up (or at least try to start it)
    _start_weather_service_if_needed()

    if token is None:
        token = get_token()

    url = f"{BASE_URL}/api/data/weather"
    params = {"lat": LAT, "lon": LON}
    headers = {"Authorization": f"Bearer {token}"}

    resp = requests.get(url, params=params, headers=headers, timeout=10)
    resp.raise_for_status()
    payload = resp.json()

    # The service may wrap data inside {"data": {...}} or return the dict directly.
    data = payload.get("data", payload)

    ts = _ts_from_unix(data.get("dt"))

    main = data.get("main", {})
    temp = main.get("temp")
    humidity = main.get("humidity")
    pressure = main.get("pressure")

    wind = data.get("wind", {})
    wind_speed = wind.get("speed")

    weather_list = data.get("weather", [])
    description = None
    if isinstance(weather_list, list) and weather_list:
        description = weather_list[0].get("description")

    return CurrentWeather(
        location_name=LOCATION_NAME,
        timestamp=ts,
        temperature=temp,
        humidity=humidity,
        pressure=pressure,
        wind_speed=wind_speed,
        description=description,
        raw=data,
    )


def fetch_forecast5(token: Optional[str] = None) -> List[ForecastPoint]:
    """
    Fetch 5-day forecast (3-hour steps) from the OpenAgri WeatherService.

    Endpoint:
        GET /api/data/forecast5?lat={lat}&lon={lon}

    Returns a list of ForecastPoint objects. This is intentionally tolerant to
    schema differences: if the WeatherService changes field names slightly,
    we still keep the raw item so we can inspect it later.
    """
    # Ensure service is up (or at least try to start it)
    _start_weather_service_if_needed()

    if token is None:
        token = get_token()

    url = f"{BASE_URL}/api/data/forecast5"
    params = {"lat": LAT, "lon": LON}
    headers = {"Authorization": f"Bearer {token}"}

    resp = requests.get(url, params=params, headers=headers, timeout=15)
    resp.raise_for_status()
    payload = resp.json()

    # Could be a list directly, or {data: [...]}, or something similar.
    items: Any = payload
    if isinstance(items, dict):
        items = items.get("data") or items.get("results") or []

    if not isinstance(items, list):
        print("[Weather] WARNING: Unexpected forecast5 payload format.")
        return []

    points: List[ForecastPoint] = []
    for item in items:
        if not isinstance(item, dict):
            continue

        ts_raw = (
            item.get("timestamp")
            or item.get("time")
            or item.get("ts")
        )
        ts = _ts_from_iso(ts_raw)

        raw_val = item.get("value")
        try:
            value = float(raw_val) if raw_val is not None else None
        except (TypeError, ValueError):
            value = None

        data_type = item.get("data_type")
        measurement_type = item.get("measurement_type")
        source = item.get("source")

        points.append(
            ForecastPoint(
                timestamp=ts,
                value=value,
                data_type=data_type,
                measurement_type=measurement_type,
                source=source,
                raw=item,
            )
        )

    return points


# ---------------------------------------------------------------------------
# Simple CLI test
# ---------------------------------------------------------------------------

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
    # Allow quick testing with: python -m agrivision.weather.client
    cw = fetch_current_weather()
    print(_format_current_weather(cw))
