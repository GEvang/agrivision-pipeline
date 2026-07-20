#!/usr/bin/env python3
"""Run the final HTML report stage for AgriVision."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, Optional, cast

from agrivision.config.settings import get_project_root
from agrivision.pipeline.report.assets import (
    ensure_report_preview,
    get_report_settings,
    load_grid_cells,
    load_json,
)
from agrivision.pipeline.report.html import (
    build_report_html,
    render_artifact_link,
    render_image_if_exists,
    render_pending_image,
    report_icon,
    safe_html,
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


def _quality_summary(vegetation_index_meta: dict[str, Any], grid_meta: dict[str, Any]) -> dict[str, str]:
    source_dataset = (
        _read_nested(vegetation_index_meta, "source", "dataset")
        or grid_meta.get("source_dataset")
        or "Source not set"
    )
    index_mode = (
        _read_nested(vegetation_index_meta, "index", "index_mode")
        or grid_meta.get("index_mode")
        or "index not set"
    )
    valid_percent = _read_nested(vegetation_index_meta, "valid_pixels", "percent")
    mean = _read_nested(vegetation_index_meta, "distribution", "mean")
    median = _read_nested(vegetation_index_meta, "distribution", "median")
    poor_max = _read_nested(grid_meta, "thresholds_used", "poor_max")
    medium_max = _read_nested(grid_meta, "thresholds_used", "medium_max")
    classification_mode = grid_meta.get("classification_mode") or "Classification not set"
    flags = vegetation_index_meta.get("quality_flags", [])

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


def _load_disease_risk_summary(
    passed_summary: Optional[Dict[str, Any]],
    summary_path: Path,
) -> dict[str, Any]:
    if passed_summary and passed_summary.get("enabled"):
        return passed_summary
    return load_json(summary_path)


def _selected_risk_layer(summary: dict[str, Any]) -> dict[str, Any] | None:
    layers = summary.get("layers")
    if not isinstance(layers, list):
        return None
    selected_key = summary.get("selected_layer_key")
    for layer in layers:
        if isinstance(layer, dict) and layer.get("profile_key") == selected_key:
            return layer
    for layer in layers:
        if isinstance(layer, dict):
            return layer
    return None


def _report_artifact_path(value: Any) -> Path | None:
    if not value:
        return None
    path = Path(str(value))
    if path.is_absolute():
        return path
    return get_project_root() / path


def _risk_target_html(summary: dict[str, Any], selected: dict[str, Any] | None) -> str:
    layers = summary.get("layers")
    if not isinstance(layers, list) or not layers:
        layers = [
            {"profile_key": "grapevine_powdery_mildew", "profile_label": "Powdery Mildew", "mean_risk": None},
            {"profile_key": "grapevine_downy_mildew", "profile_label": "Downy Mildew", "mean_risk": None},
            {"profile_key": "botrytis_bunch_rot", "profile_label": "Botrytis Bunch Rot", "mean_risk": None},
        ]
    selected_key = selected.get("profile_key") if selected else None
    icons = ["spores", "drop", "spores", "crosshair", "leaf", "pest"]
    colors = ["#6b46c1", "#2f80d0", "#8a5a2f", "#f21f18", "#22c55e", "#0f766e"]
    rows = []
    check = report_icon("check", "white", "Selected risk profile")
    for idx, layer in enumerate(layers):
        if not isinstance(layer, dict):
            continue
        is_selected = layer.get("profile_key") == selected_key
        icon = report_icon(icons[idx % len(icons)], "white", str(layer.get("profile_label") or "Risk profile"))
        mean_risk = layer.get("mean_risk")
        risk_text = f"{float(mean_risk):.2f}" if isinstance(mean_risk, (float, int)) else "N/A"
        selected_badge = f'<span class="target-badge" style="background:#f21f18;">{check}</span>' if is_selected else ""
        rows.append(
            '<div class="target{selected_class}">'
            '<span class="target-badge" style="background:{color};">{icon}</span>'
            '<strong>{label}</strong>'
            '<span class="risk-score">{risk}</span>'
            "{selected_badge}"
            "</div>".format(
                selected_class=" selected" if is_selected else "",
                color=colors[idx % len(colors)],
                icon=icon,
                label=safe_html(layer.get("profile_label") or "Risk profile"),
                risk=safe_html(risk_text),
                selected_badge=selected_badge,
            )
        )
    return "\n".join(rows)


def _risk_alert_html(selected: dict[str, Any] | None) -> str:
    if not selected:
        messages = [
            "Disease risk layer unavailable; review Vegetation Index grid and source imagery.",
            "Generate a new analysis run to calculate no-input cell risk.",
            "Use field scouting to confirm any visual anomalies.",
            "Add thermal, irrigation, and historical data to improve confidence.",
        ]
    else:
        high_count = int(selected.get("high_or_above_cells") or 0)
        mean_risk = selected.get("mean_risk")
        mean_text = f"{float(mean_risk):.2f}" if isinstance(mean_risk, (float, int)) else "N/A"
        label = str(selected.get("profile_label") or "selected profile")
        messages = [
            f"{high_count} grid cells are high risk or above for {label}.",
            f"Average final cell risk for the selected layer is {mean_text}.",
            "Prioritize scouting in red and orange cells, then adjacent yellow cells.",
            "Thermal, historical pressure, and field evidence can refine this model when available.",
        ]
    icons = ["crosshair", "search", "cloud", "leaf"]
    # `search` is not a custom icon; report_icon will fall back to notes.
    rendered = []
    for idx, message in enumerate(messages):
        rendered.append(
            f'<div class="alert-item"><span class="alert-symbol">{report_icon(icons[idx], "red")}</span>'
            f"<span>{safe_html(message)}</span></div>"
        )
    return "\n".join(rendered)


def _risk_copy(selected: dict[str, Any] | None) -> str:
    if not selected:
        return (
            "Vegetation grid overlay shown because no disease or pest risk layer was generated for this run."
        )
    missing = selected.get("missing_inputs") if isinstance(selected.get("missing_inputs"), list) else []
    missing_text = ", ".join(str(item).replace("_", " ") for item in missing) if missing else "none"
    return (
        "No-input risk score using biological seasonality, weather suitability, Vegetation Index cell anomaly, "
        f"and available context. Missing inputs reduce confidence rather than being renormalized: {missing_text}."
    )


def run_report(
    irrigation_summary: Optional[Dict[str, Any]] = None,
    weather_summary: Optional[Dict[str, Any]] = None,
    pdm_summary: Optional[Dict[str, Any]] = None,
    workspace_root: Path | None = None,
    config: dict[str, Any] | None = None,
    disease_risk_summary: Optional[Dict[str, Any]] = None,
) -> None:
    print("\n[AgriVision] Generating HTML report...")

    resolved = get_report_settings(workspace_root=workspace_root, config=config)
    output_dir = cast(Path, resolved["output_dir"])
    report_path = cast(Path, resolved["report_path"])
    vegetation_index_meta_path = cast(Path, resolved["vegetation_index_meta_path"])
    grid_meta_path = cast(Path, resolved["grid_meta_path"])
    orthophoto_rgb = cast(Path, resolved["orthophoto_rgb"])
    orthophoto_mapir = cast(Path, resolved["orthophoto_mapir"])
    orthophoto_thermal = cast(Path, resolved["orthophoto_thermal"])
    orthophoto_rgb_preview = cast(Path, resolved["orthophoto_rgb_preview"])
    orthophoto_mapir_preview = cast(Path, resolved["orthophoto_mapir_preview"])
    orthophoto_thermal_preview = cast(Path, resolved["orthophoto_thermal_preview"])
    vegetation_index_tif = cast(Path, resolved["vegetation_index_tif"])
    vegetation_index_color_png = cast(Path, resolved["vegetation_index_color_png"])
    grid_overlay_png = cast(Path, resolved["grid_overlay_png"])
    grid_cells_csv = cast(Path, resolved["grid_cells_csv"])
    grid_categories_csv = cast(Path, resolved["grid_categories_csv"])
    disease_risk_summary_path = cast(Path, resolved["disease_risk_summary"])

    output_dir.mkdir(parents=True, exist_ok=True)

    config = cast(dict[str, Any], resolved["config"])
    vegetation_index_meta = load_json(vegetation_index_meta_path)
    grid_meta = load_json(grid_meta_path)
    visible_preview = ensure_report_preview(orthophoto_rgb, orthophoto_rgb_preview)
    mapir_preview = ensure_report_preview(orthophoto_mapir, orthophoto_mapir_preview)
    thermal_preview = ensure_report_preview(orthophoto_thermal, orthophoto_thermal_preview)

    index_title = "Vegetation Index"
    weather_html = render_weather_section(weather_summary, output_dir)
    methodology_html = render_methodology_section(vegetation_index_meta)
    grid_meta_html = render_grid_metadata_section(grid_meta)

    grid_rows = load_grid_cells(grid_cells_csv)
    grid_table_html = render_grid_table(index_title=index_title, rows=grid_rows)
    irrigation_html = render_irrigation_section(irrigation_summary, output_dir)
    pdm_html = render_pdm_section(pdm_summary, output_dir)

    generated_at = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    report_quality = _quality_summary(vegetation_index_meta, grid_meta)
    risk_summary = _load_disease_risk_summary(disease_risk_summary, disease_risk_summary_path)
    selected_risk = _selected_risk_layer(risk_summary)
    risk_overlay_png = _report_artifact_path(selected_risk.get("overlay_png")) if selected_risk else None
    if risk_overlay_png is None:
        risk_overlay_png = grid_overlay_png
    risk_title = str(selected_risk.get("profile_label") or "Risk Index") if selected_risk else "Vegetation Grid Overlay"
    risk_legend_html = (
        None
        if selected_risk
        else (
            '<span><i class="dot green"></i>Green = Good</span>'
            '<span><i class="dot yellow"></i>Yellow = Medium</span>'
            '<span><i class="dot red"></i>Red = Poor</span>'
        )
    )

    artifacts_list_html = "\n".join(
        [
            render_artifact_link(f"{index_title} Map (PNG)", vegetation_index_color_png, output_dir),
            render_artifact_link(f"{index_title} GeoTIFF", vegetation_index_tif, output_dir),
            render_artifact_link("Grid Overlay (PNG)", grid_overlay_png, output_dir),
            render_artifact_link("Grid Cells (CSV)", grid_cells_csv, output_dir),
            render_artifact_link("Grid Categories (CSV)", grid_categories_csv, output_dir),
            render_artifact_link("Index Run Metadata (JSON)", vegetation_index_meta_path, output_dir),
            render_artifact_link("Grid Run Metadata (JSON)", grid_meta_path, output_dir),
            render_artifact_link("Disease Risk Summary (JSON)", disease_risk_summary_path, output_dir),
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
        visible_image_html=render_image_if_exists("RGB", visible_preview or orthophoto_rgb_preview, output_dir),
        mapir_image_html=(
            render_image_if_exists("MAPIR", mapir_preview or orthophoto_mapir_preview, output_dir)
            if mapir_preview
            else render_pending_image("MAPIR orthomosaic")
        ),
        vegetation_index_color_html=render_image_if_exists(index_title + " Map", vegetation_index_color_png, output_dir),
        thermal_image_html=(
            render_image_if_exists("Thermal Orthomosaic", thermal_preview or orthophoto_thermal_preview, output_dir)
            if thermal_preview
            else render_pending_image("Thermal orthomosaic")
        ),
        grid_meta_html=grid_meta_html,
        grid_overlay_html=render_image_if_exists(risk_title, risk_overlay_png, output_dir),
        grid_table_html=grid_table_html,
        irrigation_html=irrigation_html,
        pdm_html=pdm_html,
        risk_title=risk_title,
        risk_copy=_risk_copy(selected_risk),
        risk_layers_html=_risk_target_html(risk_summary, selected_risk),
        risk_alert_html=_risk_alert_html(selected_risk),
        risk_legend_html=risk_legend_html,
    )

    report_path.write_text(html_doc, encoding="utf-8")
    print(f"[AgriVision] Report written to: {report_path}")


if __name__ == "__main__":
    run_report()
