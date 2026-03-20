#!/usr/bin/env python3
"""Run the final HTML report stage for AgriVision."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, cast

from agrivision.pipeline.report.assets import (
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
)
from agrivision.pipeline.report.tables import render_grid_table


def run_report(irrigation_summary: Optional[Dict[str, Any]] = None) -> None:
    print("\n[AgriVision] Generating HTML report...")

    resolved = get_report_settings()
    output_dir = cast(Path, resolved["output_dir"])
    report_path = cast(Path, resolved["report_path"])
    ndvi_meta_path = cast(Path, resolved["ndvi_meta_path"])
    grid_meta_path = cast(Path, resolved["grid_meta_path"])
    ndvi_tif = cast(Path, resolved["ndvi_tif"])
    ndvi_color_png = cast(Path, resolved["ndvi_color_png"])
    grid_overlay_png = cast(Path, resolved["grid_overlay_png"])
    grid_cells_csv = cast(Path, resolved["grid_cells_csv"])
    grid_categories_csv = cast(Path, resolved["grid_categories_csv"])

    output_dir.mkdir(parents=True, exist_ok=True)

    ndvi_meta = load_json(ndvi_meta_path)
    grid_meta = load_json(grid_meta_path)

    index_title = get_index_title(ndvi_meta, grid_meta)
    methodology_html = render_methodology_section(ndvi_meta)
    grid_meta_html = render_grid_metadata_section(grid_meta)

    grid_rows = load_grid_cells(grid_cells_csv)
    grid_table_html = render_grid_table(index_title=index_title, rows=grid_rows)
    irrigation_html = render_irrigation_section(irrigation_summary, output_dir)

    generated_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

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
        methodology_html=methodology_html,
        artifacts_list_html=artifacts_list_html,
        ndvi_color_html=render_image_if_exists(index_title + " Map", ndvi_color_png, output_dir),
        grid_meta_html=grid_meta_html,
        grid_overlay_html=render_image_if_exists("Grid Overlay", grid_overlay_png, output_dir),
        grid_table_html=grid_table_html,
        irrigation_html=irrigation_html,
    )

    report_path.write_text(html_doc, encoding="utf-8")
    print(f"[AgriVision] Report written to: {report_path}")


if __name__ == "__main__":
    run_report()
