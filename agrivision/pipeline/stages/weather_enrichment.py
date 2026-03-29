from __future__ import annotations

from pathlib import Path
from typing import Any

from agrivision.integrations.weather.adapter import collect_weather_snapshot
from agrivision.pipeline.io.metadata import persist_weather_artifacts


def default_weather_summary(location_name: str) -> dict[str, Any]:
    return {
        'enabled': True,
        'location_name': location_name,
        'current_weather': {},
        'forecast5_points': [],
        'forecast5_jsonld': {},
        'thi': {},
        'thi_jsonld': {},
        'uav_flight_forecast': {},
        'spray_forecast': {},
        'spray_forecast_jsonld': {},
        'historical_daily': {},
        'historical_hourly': {},
        'notes': ['Weather integration not executed.'],
        'uav_model': 'dji_phantom4',
    }


def run_weather_enrichment(output_root: Path, location_name: str) -> dict[str, Any]:
    weather_summary = default_weather_summary(location_name)
    try:
        weather_summary = collect_weather_snapshot(uav_model='dji_phantom4')
        weather_summary = persist_weather_artifacts(weather_summary, output_root)
        return weather_summary
    except Exception as exc:  # noqa: BLE001
        weather_summary['enabled'] = False
        weather_summary['notes'] = [f'Weather integration failed: {exc}']
        return weather_summary
