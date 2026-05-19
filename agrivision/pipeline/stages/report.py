#!/usr/bin/env python3
"""Run the final HTML report stage for AgriVision."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, Optional, cast

from agrivision.config.settings import load_config
from agrivision.pipeline.report.assets import (
    ensure_report_preview,
    get_index_title,
    get_report_settings,
    load_grid_cells,
    load_json,
)
from agrivision.pipeline.report.html import (
    build_report_html,
    render_artifact_link,
    render_image_if_exists,
)
from agrivision.pipeline.report.sections import (
    render_grid_metadata_section,
    render_irrigation_section,
    render_methodology_section,
    render_pdm_section,
    render_weather_section,
)
from agrivision.pipeline.report.tables import render_grid_table


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _format_float(value: Any, precision: int = 3) -> str:
    parsed = _as_float(value)
    if parsed is None:
        return "N/A"
    return f"{parsed:.{precision}f}"


def _format_percent(value: Any) -> str:
    parsed = _as_float(value)
    if parsed is None:
        return "N/A"
    return f"{parsed:.1f}%"


def _read_nested(payload: dict[str, Any], *keys: str) -> Any:
    current: Any = payload
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _location_label(config: dict[str, Any], weather_summary: Optional[Dict[str, Any]]) -> str:
    if weather_summary:
        weather_location = weather_summary.get("location_name")
        if weather_location:
            return str(weather_location)

    location = config.get("location", {})
    if isinstance(location, dict):
        if location.get("name"):
            return str(location["name"])
        lat = location.get("lat")
        lon = location.get("lon")
        if lat is not None and lon is not None:
            return f"{lat}, {lon}"
    return "Location not set"


def _quality_summary(ndvi_meta: dict[str, Any], grid_meta: dict[str, Any]) -> dict[str, str]:
    source_dataset = (
        _read_nested(ndvi_meta, "source", "dataset")
        or grid_meta.get("source_dataset")
        or "Source not set"
    )
    index_mode = (
        _read_nested(ndvi_meta, "index", "index_mode")
        or grid_meta.get("index_mode")
        or "index not set"
    )
    valid_percent = _read_nested(ndvi_meta, "valid_pixels", "percent")
    mean = _read_nested(ndvi_meta, "distribution", "mean")
    median = _read_nested(ndvi_meta, "distribution", "median")
    poor_max = _read_nested(grid_meta, "thresholds_used", "poor_max")
    medium_max = _read_nested(grid_meta, "thresholds_used", "medium_max")
    classification_mode = grid_meta.get("classification_mode") or "Classification not set"
    flags = ndvi_meta.get("quality_flags", [])

    quality_state = "OK"
    valid_value = _as_float(valid_percent)
    if flags:
        quality_state = "Review"
    if valid_value is not None and valid_value < 20:
        quality_state = "Error"
    elif valid_value is not None and valid_value < 50:
        quality_state = "Review"

    return {
        "quality_state": quality_state,
        "source": f"{source_dataset} / {index_mode}",
        "valid_pixels": _format_percent(valid_percent),
        "mean_median": f"{_format_float(mean)} / {_format_float(median)}",
        "thresholds": f"{_format_float(poor_max)} / {_format_float(medium_max)}",
        "classification": str(classification_mode),
        "dataset": str(source_dataset),
    }


def run_report(
    irrigation_summary: Optional[Dict[str, Any]] = None,
    weather_summary: Optional[Dict[str, Any]] = None,
    pdm_summary: Optional[Dict[str, Any]] = None,
) -> None:
    print("\n[AgriVision] Generating HTML report...")

    resolved = get_report_settings()
    output_dir = cast(Path, resolved["output_dir"])
    report_path = cast(Path, resolved["report_path"])
    ndvi_meta_path = cast(Path, resolved["ndvi_meta_path"])
    grid_meta_path = cast(Path, resolved["grid_meta_path"])
    orthophoto_rgb = cast(Path, resolved["orthophoto_rgb"])
    orthophoto_mapir = cast(Path, resolved["orthophoto_mapir"])
    orthophoto_rgb_preview = cast(Path, resolved["orthophoto_rgb_preview"])
    orthophoto_mapir_preview = cast(Path, resolved["orthophoto_mapir_preview"])
    ndvi_tif = cast(Path, resolved["ndvi_tif"])
    ndvi_color_png = cast(Path, resolved["ndvi_color_png"])
    grid_overlay_png = cast(Path, resolved["grid_overlay_png"])
    grid_cells_csv = cast(Path, resolved["grid_cells_csv"])
    grid_categories_csv = cast(Path, resolved["grid_categories_csv"])

    output_dir.mkdir(parents=True, exist_ok=True)

    config = load_config()
    ndvi_meta = load_json(ndvi_meta_path)
    grid_meta = load_json(grid_meta_path)
    visible_preview = ensure_report_preview(orthophoto_rgb, orthophoto_rgb_preview)
    mapir_preview = ensure_report_preview(orthophoto_mapir, orthophoto_mapir_preview)

    index_title = get_index_title(ndvi_meta, grid_meta)
    weather_html = render_weather_section(weather_summary, output_dir)
    methodology_html = render_methodology_section(ndvi_meta)
    grid_meta_html = render_grid_metadata_section(grid_meta)

    grid_rows = load_grid_cells(grid_cells_csv)
    grid_table_html = render_grid_table(index_title=index_title, rows=grid_rows)
    irrigation_html = render_irrigation_section(irrigation_summary, output_dir)
    pdm_html = render_pdm_section(pdm_summary, output_dir)

    generated_at = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    report_quality = _quality_summary(ndvi_meta, grid_meta)

    artifacts_list_html = "\n".join(
        [
            render_artifact_link(f"{index_title} Map (PNG)", ndvi_color_png, output_dir),
            render_artifact_link(f"{index_title} GeoTIFF", ndvi_tif, output_dir),
            render_artifact_link("Grid Overlay (PNG)", grid_overlay_png, output_dir),
            render_artifact_link("Grid Cells (CSV)", grid_cells_csv, output_dir),
            render_artifact_link("Grid Categories (CSV)", grid_categories_csv, output_dir),
            render_artifact_link("Index Run Metadata (JSON)", ndvi_meta_path, output_dir),
            render_artifact_link("Grid Run Metadata (JSON)", grid_meta_path, output_dir),
        ]
    )

    html_doc = build_report_html(
        generated_at=generated_at,
        index_title=index_title,
        location_label=_location_label(config, weather_summary),
        quality=report_quality,
        weather_html=weather_html,
        methodology_html=methodology_html,
        artifacts_list_html=artifacts_list_html,
        visible_image_html=render_image_if_exists("Visible Orthomosaic", visible_preview or orthophoto_rgb_preview, output_dir),
        ndvi_color_html=render_image_if_exists(index_title + " Map", ndvi_color_png, output_dir),
        thermal_image_html=render_image_if_exists("Thermal Placeholder (MAPIR)", mapir_preview or orthophoto_mapir_preview, output_dir),
        grid_meta_html=grid_meta_html,
        grid_overlay_html=render_image_if_exists("Grid Overlay", grid_overlay_png, output_dir),
        grid_table_html=grid_table_html,
        irrigation_html=irrigation_html,
        pdm_html=pdm_html,
    )

    report_path.write_text(html_doc, encoding="utf-8")
    print(f"[AgriVision] Report written to: {report_path}")


if __name__ == "__main__":
    run_report()
