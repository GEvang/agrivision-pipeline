from __future__ import annotations

from typing import Any


def summarize_irrigation_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "authenticated": payload.get("authenticated"),
        "parcel_count": payload.get("parcel_count"),
        "eto": payload.get("eto", {}),
        "option_types": (payload.get("eto") or {}).get("option_types", {}),
        "soil_moisture": (payload.get("eto") or {}).get("soil_moisture", {}),
        "notes": payload.get("notes", []),
    }
