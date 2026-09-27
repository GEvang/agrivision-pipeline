"""Resolve a human-readable, run-local location from an orthophoto."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

import rasterio
import requests
from rasterio.warp import transform

_NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"
_USER_AGENT = "AgriVision-OpenAgri/1.0 (orthophoto-report-location)"


def _place_label(address: dict[str, Any], fallback: str) -> str:
    """Prefer a locality and its regional context over a long postal address."""
    locality = next(
        (
            str(address[key]).strip()
            for key in ("village", "town", "city", "municipality", "suburb", "hamlet")
            if address.get(key)
        ),
        "",
    )
    region = next(
        (
            str(address[key]).strip()
            for key in ("county", "state_district", "state", "region")
            if address.get(key)
        ),
        "",
    )
    if locality and region and locality.casefold() != region.casefold():
        return f"{locality}, {region}"
    return locality or region or fallback


def _reverse_geocode(latitude: float, longitude: float) -> str | None:
    """Resolve one centroid through Nominatim; failures intentionally stay non-fatal."""
    try:
        response = requests.get(
            _NOMINATIM_URL,
            params={
                "lat": f"{latitude:.7f}",
                "lon": f"{longitude:.7f}",
                "format": "jsonv2",
                "addressdetails": 1,
                "accept-language": "en",
            },
            headers={"User-Agent": _USER_AGENT},
            timeout=5,
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    fallback = str(payload.get("display_name") or "").strip()
    address = payload.get("address")
    return _place_label(address, fallback) if isinstance(address, dict) else fallback or None


def _centroid_wgs84(path: Path) -> tuple[float, float] | None:
    try:
        with rasterio.open(path) as src:
            if src.crs is None or src.width < 1 or src.height < 1:
                return None
            x, y = src.transform * (src.width / 2, src.height / 2)
            longitude, latitude = transform(src.crs, "EPSG:4326", [x], [y])
    except (OSError, rasterio.errors.RasterioError, ValueError):
        return None
    return float(latitude[0]), float(longitude[0])


def resolve_orthophoto_location(paths: Iterable[Path]) -> dict[str, Any] | None:
    """Return the first georeferenced orthophoto's place label and centroid."""
    for path in paths:
        if not path.exists():
            continue
        centroid = _centroid_wgs84(path)
        if centroid is None:
            continue
        latitude, longitude = centroid
        coordinate_label = f"{latitude:.5f}, {longitude:.5f}"
        place_label = _reverse_geocode(latitude, longitude)
        return {
            "label": place_label or coordinate_label,
            "latitude": latitude,
            "longitude": longitude,
            "source_path": str(path),
            "geocoded": bool(place_label),
        }
    return None
