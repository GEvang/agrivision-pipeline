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
  - current weather (already integrated in your previous test)

You can later extend this with forecast, THI, spray windows, etc.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict

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
# Data model
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ts_from_unix(ts: int | float | None) -> datetime | None:
    if ts is None:
        return None
    return datetime.fromtimestamp(ts)


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


def fetch_current_weather(token: str | None = None) -> CurrentWeather:
    """
    Fetch current weather from the OpenAgri WeatherService.

    Endpoint:
        GET /api/data/weather?lat={lat}&lon={lon}

    The service currently returns a JSON payload with OpenWeather-like fields,
    e.g.:

      {
        "dt": 1764765075,
        "main": {"humidity": 64, "pressure": 1018, "temp": 20.38},
        "weather": [{"description": "overcast clouds"}],
        "wind": {"speed": 3.93}
      }

    We normalize this into a CurrentWeather dataclass.
    """
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

