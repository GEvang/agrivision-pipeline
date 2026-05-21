"""No-input disease and pest risk scoring."""

from __future__ import annotations

import csv
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import matplotlib.patheffects as path_effects
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Rectangle

from agrivision.pipeline.grid.render import _read_rgb_background
from agrivision.pipeline.risk.profiles import profiles_for_crop

RISK_COLORS = {
    "very_low": "#2768d9",
    "low": "#1fa447",
    "medium": "#f5c400",
    "high": "#ef1d16",
    "very_high": "#b91c1c",
}
DRIVER_WEIGHTS = {
    "weather": 0.40,
    "ndvi_anomaly": 0.20,
    "thermal_anomaly": 0.20,
    "historical_pressure": 0.10,
    "soil_irrigation": 0.10,
}


def _to_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if np.isfinite(parsed) else None


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        text = str(value).replace("Z", "+00:00")
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _load_grid_cells(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            row["mean_index"] = _to_float(row.get("mean_index"))
            row["valid_fraction"] = _to_float(row.get("valid_fraction")) or 0.0
            for key in ("r0", "r1", "c0", "c1"):
                try:
                    row[key] = int(row.get(key) or 0)
                except (TypeError, ValueError):
                    row[key] = 0
            rows.append(row)
    return rows


def _score_range(value: float | None, ranges: list[tuple[float | None, float | None, float]]) -> float | None:
    if value is None:
        return None
    for lower, upper, score in ranges:
        if lower is not None and value < lower:
            continue
        if upper is not None and value >= upper:
            continue
        return float(score)
    return None


def _risk_category(score: float | None) -> str:
    if score is None:
        return "no_data"
    if score < 0.15:
        return "very_low"
    if score < 0.30:
        return "low"
    if score < 0.50:
        return "medium"
    if score < 0.70:
        return "high"
    return "very_high"


def _extract_weather_values(weather_summary: dict[str, Any]) -> dict[str, float | None]:
    current = weather_summary.get("current_weather", {})
    if not isinstance(current, dict):
        current = {}
    raw = current.get("raw", {})
    if not isinstance(raw, dict):
        raw = {}
    rain = raw.get("rain", {})
    precipitation = None
    if isinstance(rain, dict):
        precipitation = _to_float(rain.get("1h")) or _to_float(rain.get("3h"))
    return {
        "temperature": _to_float(current.get("temperature")),
        "humidity": _to_float(current.get("humidity")),
        "wind_speed": _to_float(current.get("wind_speed")),
        "precipitation": precipitation or _recent_precipitation(weather_summary),
    }


def _recent_precipitation(weather_summary: dict[str, Any]) -> float | None:
    hourly = weather_summary.get("historical_hourly", {})
    values: list[float] = []
    for item in _walk_values(hourly):
        if isinstance(item, dict):
            for key in ("precipitation", "rain", "rainfall", "precipitation_sum"):
                value = _to_float(item.get(key))
                if value is not None:
                    values.append(value)
    if values:
        return float(sum(values[-48:]))
    return None


def _walk_values(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_values(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_values(child)


def _weather_suitability(profile: dict[str, Any], weather_summary: dict[str, Any]) -> tuple[float | None, dict[str, float | None]]:
    values = _extract_weather_values(weather_summary)
    components = {
        "temperature": _score_range(values["temperature"], profile["temperature"]),
        "humidity": _score_range(values["humidity"], profile["humidity"]),
        "rain": _score_range(values["precipitation"], profile["rain"]),
        "wind": _score_range(values["wind_speed"], profile["wind"]),
    }
    weights = {"temperature": 0.45, "humidity": 0.25, "rain": 0.15, "wind": 0.15}
    weighted = sum(weights[key] * value for key, value in components.items() if value is not None)
    available = sum(weights[key] for key, value in components.items() if value is not None)
    score = weighted / available if available else None
    return score, components


def _ndvi_anomaly_scores(cells: list[dict[str, Any]]) -> dict[str, float | None]:
    values = np.array([row["mean_index"] for row in cells if row.get("mean_index") is not None], dtype="float32")
    if values.size < 2:
        return {str(row["cell_id"]): None for row in cells}
    low, high = np.nanpercentile(values, [5, 95])
    if high <= low:
        return {str(row["cell_id"]): 0.0 for row in cells}
    scores: dict[str, float | None] = {}
    for row in cells:
        value = row.get("mean_index")
        if value is None:
            scores[str(row["cell_id"])] = None
            continue
        scores[str(row["cell_id"])] = float(np.clip((high - float(value)) / (high - low), 0.0, 1.0))
    return scores


def _irrigation_score(irrigation_summary: dict[str, Any] | None) -> float | None:
    if not irrigation_summary or not irrigation_summary.get("authenticated"):
        return None
    eto = irrigation_summary.get("eto", {})
    if isinstance(eto, dict) and eto.get("ok"):
        return 0.4
    return None


def _capture_month(ndvi_meta: dict[str, Any], grid_meta: dict[str, Any], weather_summary: dict[str, Any]) -> int:
    candidates = [
        weather_summary.get("current_weather", {}).get("timestamp") if isinstance(weather_summary.get("current_weather"), dict) else None,
        ndvi_meta.get("generated_at_utc"),
        grid_meta.get("generated_at_utc"),
    ]
    for candidate in candidates:
        parsed = _parse_datetime(candidate)
        if parsed is not None:
            return parsed.month
    return datetime.utcnow().month


def _score_profile(
    profile: dict[str, Any],
    cells: list[dict[str, Any]],
    month: int,
    weather_summary: dict[str, Any],
    irrigation_summary: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    seasonality = float(profile["seasonality"].get(month, 0.0))
    phenology = 1.0
    biological_gate = seasonality * phenology
    weather_score, weather_components = _weather_suitability(profile, weather_summary)
    ndvi_scores = _ndvi_anomaly_scores(cells)
    soil_irrigation = _irrigation_score(irrigation_summary)

    scored: list[dict[str, Any]] = []
    for row in cells:
        cell_id = str(row["cell_id"])
        components = {
            "weather": weather_score,
            "ndvi_anomaly": ndvi_scores.get(cell_id),
            "thermal_anomaly": None,
            "historical_pressure": None,
            "soil_irrigation": soil_irrigation,
        }
        weighted_sum = sum(DRIVER_WEIGHTS[key] * value for key, value in components.items() if value is not None)
        available_weight = sum(DRIVER_WEIGHTS[key] for key, value in components.items() if value is not None)
        driver = weighted_sum / available_weight if available_weight else None
        final = biological_gate * driver if driver is not None else None
        scored.append(
            {
                **row,
                "profile_key": profile["key"],
                "profile_label": profile["label"],
                "seasonality_score": seasonality,
                "phenology_score": phenology,
                "biological_gate": biological_gate,
                "weather_suitability": weather_score,
                "ndvi_anomaly": components["ndvi_anomaly"],
                "thermal_anomaly": components["thermal_anomaly"],
                "historical_pressure": components["historical_pressure"],
                "soil_irrigation": components["soil_irrigation"],
                "available_weight": available_weight,
                "risk_driver": driver,
                "final_risk": final,
                "risk_category": _risk_category(final),
            }
        )

    valid_scores = [row["final_risk"] for row in scored if row["final_risk"] is not None]
    summary = {
        "profile_key": profile["key"],
        "profile_label": profile["label"],
        "organism_name": profile.get("organism_name", ""),
        "crop": profile["crop"],
        "seasonality_score": seasonality,
        "phenology_score": phenology,
        "biological_gate": biological_gate,
        "weather_suitability": weather_score,
        "weather_components": weather_components,
        "mean_risk": float(np.mean(valid_scores)) if valid_scores else None,
        "max_risk": float(np.max(valid_scores)) if valid_scores else None,
        "high_or_above_cells": sum(1 for value in valid_scores if value >= 0.5),
        "used_inputs": sorted({key for key in DRIVER_WEIGHTS if any(row.get(key) is not None for row in scored)}),
        "missing_inputs": ["thermal_anomaly", "historical_pressure"] + ([] if soil_irrigation is not None else ["soil_irrigation"]),
    }
    return scored, summary


def _save_profile_csv(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "cell_id",
        "row_label",
        "col_label",
        "mean_index",
        "valid_fraction",
        "seasonality_score",
        "phenology_score",
        "biological_gate",
        "weather_suitability",
        "ndvi_anomaly",
        "thermal_anomaly",
        "historical_pressure",
        "soil_irrigation",
        "available_weight",
        "risk_driver",
        "final_risk",
        "risk_category",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _format_csv_value(row.get(key)) for key in fieldnames})


def _format_csv_value(value: Any) -> Any:
    if isinstance(value, float):
        return f"{value:.4f}"
    if value is None:
        return ""
    return value


def _save_risk_overlay(rows: list[dict[str, Any]], row_edges: np.ndarray, col_edges: np.ndarray, out_path: Path, background_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    shape = (int(row_edges[-1]), int(col_edges[-1]))
    background = _read_rgb_background(background_path, shape)
    plt.figure(figsize=(8, 8))
    if background is not None:
        image, scale = background
        plt.imshow(image, origin="upper")
    else:
        scale = min(1.0, 2500 / float(max(shape)))
        plt.imshow(np.ones((max(1, int(shape[0] * scale)), max(1, int(shape[1] * scale)), 3)), origin="upper")
    plt.axis("off")
    ax = plt.gca()
    for row in rows:
        if row.get("final_risk") is None:
            continue
        r0, r1 = int(row["r0"]), int(row["r1"])
        c0, c1 = int(row["c0"]), int(row["c1"])
        category = str(row["risk_category"])
        color = RISK_COLORS.get(category, "#8a8f98")
        ax.add_patch(
            Rectangle(
                (c0 * scale, r0 * scale),
                max((c1 - c0) * scale, 1),
                max((r1 - r0) * scale, 1),
                facecolor=color,
                edgecolor="white",
                linewidth=0.7,
                alpha=0.50,
                zorder=2,
            )
        )
        text = plt.text(
            ((c0 + c1) / 2.0) * scale,
            ((r0 + r1) / 2.0) * scale,
            str(row["cell_id"]),
            color="white",
            fontsize=7,
            ha="center",
            va="center",
            fontweight="bold",
            zorder=4,
        )
        text.set_path_effects([path_effects.withStroke(linewidth=1.2, foreground="black", alpha=0.65)])
    for x in col_edges:
        plt.axvline(x=x * scale, color="white", linewidth=0.45, alpha=0.65, zorder=3)
    for y in row_edges:
        plt.axhline(y=y * scale, color="white", linewidth=0.45, alpha=0.65, zorder=3)
    plt.tight_layout(pad=0)
    plt.savefig(out_path, dpi=300, bbox_inches="tight", pad_inches=0)
    plt.close()


def run_disease_risk_scoring(
    *,
    crop: str | None,
    ndvi_dir: Path,
    rgb_orthophoto: Path,
    weather_summary: dict[str, Any],
    irrigation_summary: dict[str, Any] | None,
) -> dict[str, Any]:
    grid_csv = ndvi_dir / "ndvi_grid_cells.csv"
    grid_meta_path = ndvi_dir / "grid_metadata.json"
    ndvi_meta_path = ndvi_dir / "metadata.json"
    cells = _load_grid_cells(grid_csv)
    if not cells:
        return {"enabled": False, "notes": ["No grid cells available for disease risk scoring."], "layers": []}
    grid_meta = _load_json(grid_meta_path)
    ndvi_meta = _load_json(ndvi_meta_path)
    grid_shape = grid_meta.get("grid", {}) if isinstance(grid_meta.get("grid"), dict) else {}
    rows = int(grid_shape.get("rows") or len({row.get("row_label") for row in cells}) or 1)
    cols = int(grid_shape.get("cols") or max(int(row.get("col_label") or 1) for row in cells))
    max_row_edge = max(int(row.get("r1", 0)) for row in cells)
    max_col_edge = max(int(row.get("c1", 0)) for row in cells)
    if max_row_edge <= 0 or max_col_edge <= 0:
        return {
            "enabled": False,
            "notes": ["Grid cell bounds are unavailable. Generate a new grid before disease risk scoring."],
            "layers": [],
        }
    row_edges = np.linspace(0, max_row_edge, rows + 1, dtype=int)
    col_edges = np.linspace(0, max_col_edge, cols + 1, dtype=int)
    month = _capture_month(ndvi_meta, grid_meta, weather_summary)
    out_dir = ndvi_dir / "disease_risk"
    out_dir.mkdir(parents=True, exist_ok=True)

    layers: list[dict[str, Any]] = []
    for profile in profiles_for_crop(crop):
        scored_rows, summary = _score_profile(profile, cells, month, weather_summary, irrigation_summary)
        csv_path = out_dir / f"{profile['key']}_cells.csv"
        png_path = out_dir / f"{profile['key']}_overlay.png"
        _save_profile_csv(scored_rows, csv_path)
        _save_risk_overlay(scored_rows, row_edges, col_edges, png_path, rgb_orthophoto)
        summary["cells_csv"] = str(csv_path)
        summary["overlay_png"] = str(png_path)
        layers.append(summary)

    selected = max(layers, key=lambda item: item.get("mean_risk") or 0.0) if layers else None
    payload = {
        "enabled": True,
        "generated_at_utc": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "crop": crop or "grapevine",
        "capture_month_used": month,
        "formula": {
            "biological_gate": "seasonality_score * phenology_score",
            "risk_driver": DRIVER_WEIGHTS,
            "missing_inputs": "Weights are renormalized over available inputs.",
            "final_cell_risk": "biological_gate * normalized_available_risk_driver",
        },
        "selected_layer_key": selected.get("profile_key") if selected else None,
        "selected_layer_label": selected.get("profile_label") if selected else None,
        "layers": layers,
    }
    summary_path = out_dir / "summary.json"
    summary_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    payload["summary_json"] = str(summary_path)
    return payload
