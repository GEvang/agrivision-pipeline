"""Parcel geometry in the coordinate order the OpenAgri services expect.

The OpenAgri Irrigation and Pest & Disease services read WKT with
``x = latitude`` and ``y = longitude`` (``c_latitude = geometry.centroid.x``
in both services, and their documented example is
``POLYGON ((40.2 21.2, ...))``). That is the reverse of the WKT/GeoJSON
standard, which is ``(longitude latitude)``. Build and parse parcel WKT only
through these helpers so the order is never "corrected" by accident.
"""

from __future__ import annotations


def openagri_point_wkt(latitude: float, longitude: float) -> str:
    """Return a parcel point as OpenAgri services read it: ``POINT (lat lon)``."""
    return f"POINT ({latitude:.7f} {longitude:.7f})"


def parse_openagri_point_wkt(wkt: str) -> tuple[float, float] | None:
    """Return ``(latitude, longitude)`` from an OpenAgri ``POINT (lat lon)``."""
    text = (wkt or "").strip()
    if not text.upper().startswith("POINT"):
        return None
    try:
        coords = text[text.index("(") + 1 : text.rindex(")")].replace(",", " ").split()
        return float(coords[0]), float(coords[1])
    except (IndexError, ValueError):
        return None
