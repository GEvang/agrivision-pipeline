from __future__ import annotations

from pathlib import Path
from typing import Any

from .artifacts import write_json


def persist_weather_artifacts(weather_summary: dict[str, Any], output_root: Path) -> dict[str, Any]:
    weather_dir = output_root / 'weather'
    weather_dir.mkdir(parents=True, exist_ok=True)
    mapping = {
        'current_weather_artifact': ('current_weather.json', weather_summary.get('current_weather', {})),
        'forecast_json_artifact': ('forecast5.json', weather_summary.get('forecast5_points', [])),
        'forecast_jsonld_artifact': ('forecast5.jsonld', weather_summary.get('forecast5_jsonld', {})),
        'thi_artifact': ('thi.json', weather_summary.get('thi', {})),
        'thi_jsonld_artifact': ('thi.jsonld', weather_summary.get('thi_jsonld', {})),
        'uav_artifact': ('uav_flight_forecast.json', weather_summary.get('uav_flight_forecast', {})),
        'spray_artifact': ('spray_forecast.json', weather_summary.get('spray_forecast', {})),
        'spray_jsonld_artifact': ('spray_forecast.jsonld', weather_summary.get('spray_forecast_jsonld', {})),
        'historical_daily_artifact': ('historical_daily.json', weather_summary.get('historical_daily', {})),
        'historical_hourly_artifact': ('historical_hourly.json', weather_summary.get('historical_hourly', {})),
    }
    for key, (filename, payload) in mapping.items():
        weather_summary[key] = write_json(weather_dir / filename, payload)
    return weather_summary
