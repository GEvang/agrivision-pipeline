from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from agrivision.app import dependencies as deps
from agrivision.app.formatters import step_summary
from agrivision.app.health import service_health
from agrivision.app.schemas.runs import RunRecord
from agrivision.config import load_config
from agrivision.services.service_control import missing_service_repos, service_controls
from agrivision.services.weather.client import _authorized_get, get_token

router = APIRouter()


def _read_json(path: Path) -> dict[str, Any] | list[Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _format_weather_location(name: str | None) -> str:
    if not name:
        return "Unknown location"
    parts = [part.strip() for part in str(name).split(",") if part.strip()]
    return ", ".join(parts[:2]) if parts else "Unknown location"


def _title_case_description(text: str | None) -> str:
    if not text:
        return "Weather unavailable"
    return " ".join(word.capitalize() for word in str(text).split())


def _weather_icon_key(description: str | None, precipitation: float | None = None) -> str:
    desc = (description or "").lower()
    if "storm" in desc or "thunder" in desc:
        return "thunderstorm"
    if precipitation is not None and precipitation > 0.4:
        return "rain"
    if "rain" in desc or "storm" in desc or "drizzle" in desc:
        return "rain"
    if "cloud" in desc or "overcast" in desc:
        return "cloud"
    return "sun"


def _default_dashboard_weather(*, message: str, location: str = "Run an analysis first") -> dict[str, object]:
    return {
        "available": False,
        "location": location,
        "temperature": "--",
        "description": "Weather unavailable",
        "feels_like": message,
        "rain_chance": "--",
        "wind": "--",
        "humidity": "--",
        "forecast": [],
        "icon": "cloud",
        "message": message,
    }


def _forecast_rows_from_series(series: list[dict[str, Any]]) -> list[dict[str, str | None]]:
    grouped: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for item in series:
        timestamp = item.get("timestamp")
        measurement_type = item.get("measurement_type")
        value = _safe_float(item.get("value"))
        if not timestamp or not measurement_type or value is None:
            continue
        try:
            dt = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
        except ValueError:
            continue
        grouped[dt.date().isoformat()][measurement_type].append(value)

    rows: list[dict[str, str | None]] = []
    for date_key, metrics in sorted(grouped.items())[:5]:
        dt = datetime.fromisoformat(date_key)
        temps = metrics.get("ambient_temperature", [])
        humidity = metrics.get("ambient_humidity", [])
        precipitation = metrics.get("precipitation", [])
        rows.append(
            {
                "day": dt.strftime("%a"),
                "high": f"{round(max(temps))}°C" if temps else None,
                "low": f"{round(min(temps))}°C" if temps else None,
                "icon": _weather_icon_key(None, max(precipitation) if precipitation else None),
                "humidity": f"{round(sum(humidity) / len(humidity))}%" if humidity else None,
            }
        )
    return rows


def _crop_details(run: RunRecord) -> dict[str, str]:
    crop = str(run.parameters.get("pdm_crop") or "").strip().lower()
    if crop == "olive":
        return {"label": "Olive", "icon": "olive.png"}
    if crop == "grapevine":
        return {"label": "Grape", "icon": "grape.png"}
    return {"label": "Not set", "icon": "report.png"}


def _run_type_label(run: RunRecord) -> str:
    return "Orthophoto Build" if run.selected_steps.run_odm else "Field Analysis"


def _health_score(quality: dict[str, Any]) -> int | None:
    mean = _safe_float(quality.get("mean"))
    if mean is None:
        return None
    return int(round((mean + 1.0) * 50.0))


def _health_tone(score: int | None) -> str:
    if score is None:
        return "muted"
    if score >= 70:
        return "good"
    if score >= 40:
        return "warn"
    return "bad"


def _status_icon(status: str) -> str:
    if status == "completed":
        return "done"
    if status in {"running", "queued"}:
        return "progress"
    if status in {"failed", "cancelled"}:
        return "failed"
    return "idle"


def _report_card(run: RunRecord, report) -> dict[str, Any]:
    quality = report.quality if report else {}
    score = _health_score(quality)
    return {
        "run": run,
        "report": report,
        "quality": quality,
        "crop": _crop_details(run),
        "type_label": _run_type_label(run),
        "health_score": score,
        "health_tone": _health_tone(score),
        "status_icon": _status_icon(run.status),
    }


def _latest_report_weather_context() -> tuple[object | None, dict[str, Any] | None, list[dict[str, Any]] | None]:
    latest_report = deps.report_service.latest_report(generate_preview=False)
    if latest_report is None:
        return None, None, None
    run = deps.run_service.load_run(latest_report.run_id)
    weather_dir = Path(run.run_dir) / "workspace" / "output" / "weather"
    current_candidate = _read_json(weather_dir / "current_weather.json")
    forecast_candidate = _read_json(weather_dir / "forecast5.json")
    current_payload = current_candidate if isinstance(current_candidate, dict) else None
    forecast_payload = [item for item in forecast_candidate if isinstance(item, dict)] if isinstance(forecast_candidate, list) else None
    return latest_report, current_payload, forecast_payload


def _live_weather_for_location(
    *,
    current_payload: dict[str, Any] | None,
    location_name: str,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]] | None]:
    config = load_config()
    location_cfg = config.get("location", {})
    lat = _safe_float(location_cfg.get("lat"))
    lon = _safe_float(location_cfg.get("lon"))
    if lat is None or lon is None:
        return current_payload, None

    token = get_token()
    current_response = _authorized_get(
        "/api/data/weather",
        token=token,
        params={"lat": lat, "lon": lon},
        timeout=10,
    )
    current_data = current_response.get("data", current_response) if isinstance(current_response, dict) else {}
    if not isinstance(current_data, dict):
        current_data = {}
    current_data = {
        "location_name": location_name,
        "temperature": current_data.get("temperature", (current_payload or {}).get("temperature")),
        "humidity": current_data.get("humidity", (current_payload or {}).get("humidity")),
        "pressure": current_data.get("pressure", (current_payload or {}).get("pressure")),
        "wind_speed": current_data.get("wind_speed", (current_payload or {}).get("wind_speed")),
        "description": current_data.get("conditions") or current_data.get("description") or (current_payload or {}).get("description"),
        "raw": current_data,
    }

    forecast_response = _authorized_get(
        "/api/data/forecast5",
        token=token,
        params={"lat": lat, "lon": lon},
        timeout=15,
    )
    forecast_data = forecast_response.get("data", forecast_response) if isinstance(forecast_response, dict) else forecast_response
    forecast_payload = [item for item in forecast_data if isinstance(item, dict)] if isinstance(forecast_data, list) else []
    return current_data, forecast_payload


def _load_dashboard_weather() -> dict[str, object]:
    latest_report, current_payload, forecast_payload = _latest_report_weather_context()
    if latest_report is None:
        return _default_dashboard_weather(message="Run an analysis first to populate dashboard weather.")

    location_name = _format_weather_location((current_payload or {}).get("location_name") or latest_report.dataset_name)

    try:
        current_payload, live_forecast = _live_weather_for_location(current_payload=current_payload, location_name=location_name)
        if live_forecast:
            forecast_payload = live_forecast
    except Exception:
        pass

    if not current_payload:
        return _default_dashboard_weather(
            message="Weather data is not available for the latest analysis yet.",
            location=location_name,
        )

    current_raw = current_payload.get("raw", {}) if isinstance(current_payload, dict) else {}
    main_raw = current_raw.get("main", {}) if isinstance(current_raw, dict) else {}
    temp = _safe_float(current_payload.get("temperature")) if isinstance(current_payload, dict) else None
    feels_like = _safe_float(main_raw.get("feels_like")) if isinstance(main_raw, dict) else None
    humidity = _safe_float(current_payload.get("humidity")) if isinstance(current_payload, dict) else None
    wind_speed = _safe_float(current_payload.get("wind_speed")) if isinstance(current_payload, dict) else None
    forecast_rows = _forecast_rows_from_series(forecast_payload or [])

    today_precip = None
    for row in (forecast_payload or [])[:12]:
        if row.get("measurement_type") == "precipitation":
            value = _safe_float(row.get("value"))
            if value is not None:
                today_precip = value
                break

    rain_chance = None
    if today_precip is not None:
        rain_chance = min(100, max(0, round(today_precip * 45)))

    return {
        "available": True,
        "location": location_name,
        "temperature": f"{round(temp)}°C" if temp is not None else "--",
        "description": _title_case_description((current_payload or {}).get("description")),
        "feels_like": f"Feels like {round(feels_like if feels_like is not None else temp)}°C" if temp is not None else "Weather unavailable",
        "rain_chance": f"{rain_chance}%" if rain_chance is not None else "--",
        "wind": f"{round(wind_speed * 3.6)} km/h" if wind_speed is not None else "--",
        "humidity": f"{round(humidity)}%" if humidity is not None else "--",
        "forecast": forecast_rows,
        "icon": _weather_icon_key((current_payload or {}).get("description"), today_precip),
        "message": "",
    }


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request) -> HTMLResponse:
    runs = deps.run_service.list_runs()
    status_summary: dict[str, int] = {}
    for run in runs:
        status_summary[run.status] = status_summary.get(run.status, 0) + 1
    reports = deps.report_service.list_reports(generate_previews=True)
    report_lookup = {item.run_id: item for item in reports}
    latest_report = next((item for item in reports if item.report_path), None)
    latest_run = deps.run_service.load_run(latest_report.run_id) if latest_report else None
    latest_card = _report_card(latest_run, latest_report) if latest_run and latest_report else None
    recent_run_cards = [_report_card(run, report_lookup.get(run.run_id)) for run in runs[:10]]
    active_runs = sum(1 for run in runs if run.status in {"queued", "running"})
    return deps.templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "recent_run_cards": recent_run_cards,
            "total_runs": len(runs),
            "active_runs": active_runs,
            "status_summary": status_summary,
            "latest_report": latest_report,
            "latest_card": latest_card,
            "service_health": service_health(),
            "missing_services": missing_service_repos(),
            "service_controls": service_controls(),
            "step_summary": step_summary,
            "dashboard_weather": _load_dashboard_weather(),
        },
    )
