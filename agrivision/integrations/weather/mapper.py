from __future__ import annotations

from typing import Any


def summarize_weather_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "location_name": payload.get("location_name"),
        "current_weather": payload.get("current_weather", {}),
        "notes": payload.get("notes", []),
    }
