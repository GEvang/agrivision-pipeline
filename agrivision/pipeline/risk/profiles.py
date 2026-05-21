"""No-input disease risk profiles derived from the AgriVision scoring sheets."""

from __future__ import annotations

from typing import Any

MONTHS = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")


def _months(values: dict[str, float]) -> dict[int, float]:
    return {idx + 1: float(values.get(name, 0.0)) for idx, name in enumerate(MONTHS)}


DISEASE_RISK_PROFILES: list[dict[str, Any]] = [
    {
        "key": "grapevine_powdery_mildew",
        "crop": "grapevine",
        "label": "Grapevine Powdery Mildew",
        "organism_name": "Erysiphe necator",
        "seasonality": _months(
            {
                "jan": 0.0,
                "feb": 0.0,
                "mar": 0.2,
                "apr": 0.6,
                "may": 1.0,
                "jun": 1.0,
                "jul": 0.8,
                "aug": 0.6,
                "sep": 0.3,
                "oct": 0.1,
                "nov": 0.0,
                "dec": 0.0,
            }
        ),
        "temperature": [(None, 10, 0.05), (10, 15, 0.30), (15, 21, 0.70), (21, 29, 1.00), (29, 35, 0.50), (35, None, 0.05)],
        "humidity": [(None, 35, 0.20), (35, 50, 0.50), (50, 85, 1.00), (85, None, 0.70)],
        "rain": [(0, 0.1, 0.60), (0.1, 2, 0.70), (2, 8, 0.40), (8, None, 0.20)],
        "wind": [(None, 2, 0.80), (2, 5, 0.90), (5, None, 0.60)],
    },
    {
        "key": "grapevine_downy_mildew",
        "crop": "grapevine",
        "label": "Grapevine Downy Mildew",
        "organism_name": "Plasmopara viticola",
        "seasonality": _months({"jan": 0.05, "feb": 0.05, "mar": 0.2, "apr": 0.7, "may": 1.0, "jun": 1.0, "jul": 0.7, "aug": 0.5, "sep": 0.6, "oct": 0.3, "nov": 0.05, "dec": 0.05}),
        "temperature": [(None, 10, 0.05), (10, 13, 0.30), (13, 18, 0.70), (18, 25, 1.00), (25, 30, 0.60), (30, None, 0.10)],
        "humidity": [(None, 50, 0.05), (50, 65, 0.30), (65, 80, 0.70), (80, None, 1.00)],
        "rain": [(0, 0.1, 0.05), (0.1, 2, 0.40), (2, 8, 0.80), (8, 20, 1.00), (20, None, 0.70)],
        "wind": [(None, 2, 0.90), (2, 5, 0.70), (5, None, 0.40)],
    },
    {
        "key": "botrytis_bunch_rot",
        "crop": "grapevine",
        "label": "Botrytis Bunch Rot",
        "organism_name": "Botrytis cinerea",
        "seasonality": _months({"jan": 0.0, "feb": 0.0, "mar": 0.1, "apr": 0.2, "may": 0.5, "jun": 0.4, "jul": 0.3, "aug": 0.7, "sep": 1.0, "oct": 0.9, "nov": 0.1, "dec": 0.1}),
        "temperature": [(None, 10, 0.10), (10, 14, 0.50), (14, 28, 1.00), (28, 32, 0.40), (32, None, 0.10)],
        "humidity": [(None, 70, 0.10), (70, 85, 0.40), (85, 92, 0.70), (92, None, 1.00)],
        "rain": [(0, 0.1, 0.05), (0.1, 2, 0.40), (2, 8, 0.80), (8, 20, 1.00), (20, None, 0.80)],
        "wind": [(None, 2, 0.90), (2, 5, 0.70), (5, None, 0.40)],
    },
    {
        "key": "olive_peacock_spot",
        "crop": "olive",
        "label": "Olive Peacock Spot",
        "organism_name": "Venturia oleaginea / Spilocaea oleagina",
        "seasonality": _months({"jan": 0.9, "feb": 0.9, "mar": 0.8, "apr": 0.7, "may": 0.45, "jun": 0.15, "jul": 0.05, "aug": 0.1, "sep": 0.4, "oct": 0.8, "nov": 1.0, "dec": 1.0}),
        "temperature": [(None, 7, 0.20), (7, 12, 0.70), (12, 18, 1.00), (18, 22, 0.75), (22, 26, 0.35), (26, None, 0.05)],
        "humidity": [(None, 50, 0.05), (50, 65, 0.30), (65, 80, 0.75), (80, None, 1.00)],
        "rain": [(0, 0.1, 0.05), (0.1, 2, 0.30), (2, 8, 0.80), (8, 20, 1.00), (20, None, 0.55)],
        "wind": [(None, 2, 0.90), (2, 5, 0.60), (5, None, 0.25)],
    },
    {
        "key": "olive_fruit_fly_dacus",
        "crop": "olive",
        "label": "Olive Fruit Fly (Dacus)",
        "organism_name": "Bactrocera oleae",
        "seasonality": _months({"jan": 0.05, "feb": 0.05, "mar": 0.05, "apr": 0.1, "may": 0.2, "jun": 0.5, "jul": 0.7, "aug": 0.8, "sep": 1.0, "oct": 1.0, "nov": 0.7, "dec": 0.1}),
        "temperature": [(None, 10, 0.00), (10, 15, 0.20), (15, 20, 0.50), (20, 28, 1.00), (28, 30, 0.70), (30, 32, 0.25), (32, None, 0.05)],
        "humidity": [(None, 35, 0.10), (35, 50, 0.40), (50, 65, 0.70), (65, None, 1.00)],
        "rain": [(0, 0.1, 0.20), (0.1, 2, 0.50), (2, 8, 0.80), (8, 20, 1.00), (20, None, 0.40)],
        "wind": [(None, 2, 1.00), (2, 5, 0.60), (5, None, 0.30)],
    },
    {
        "key": "olive_anthracnose_gloeosporium",
        "crop": "olive",
        "label": "Olive Anthracnose / Gloeosporium",
        "organism_name": "Colletotrichum spp.",
        "seasonality": _months({"jan": 0.3, "feb": 0.3, "mar": 0.25, "apr": 0.2, "may": 0.2, "jun": 0.1, "jul": 0.1, "aug": 0.2, "sep": 0.6, "oct": 1.0, "nov": 1.0, "dec": 0.8}),
        "temperature": [(None, 10, 0.20), (10, 15, 0.70), (15, 22, 1.00), (22, 25, 0.70), (25, 30, 0.30), (30, None, 0.05)],
        "humidity": [(None, 50, 0.10), (50, 65, 0.40), (65, 80, 0.75), (80, None, 1.00)],
        "rain": [(0, 0.1, 0.10), (0.1, 2, 0.40), (2, 8, 0.80), (8, 20, 1.00), (20, None, 0.50)],
        "wind": [(None, 2, 0.90), (2, 5, 0.60), (5, None, 0.25)],
    },
]


def profiles_for_crop(crop: str | None) -> list[dict[str, Any]]:
    if not crop:
        return [profile for profile in DISEASE_RISK_PROFILES if profile["crop"] == "grapevine"]
    crop_key = crop.strip().lower()
    profiles = [profile for profile in DISEASE_RISK_PROFILES if profile["crop"] == crop_key]
    return profiles or [profile for profile in DISEASE_RISK_PROFILES if profile["crop"] == "grapevine"]
