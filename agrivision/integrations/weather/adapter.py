from __future__ import annotations

from typing import Any

from .client import collect_weather_summary
from .mapper import summarize_weather_payload


def collect_weather_snapshot(
    uav_model: str = "dji_phantom4", *, location: dict[str, Any] | None = None
) -> dict[str, Any]:
    payload = collect_weather_summary(uav_model=uav_model, location=location)
    payload["summary"] = summarize_weather_payload(payload)
    return payload
