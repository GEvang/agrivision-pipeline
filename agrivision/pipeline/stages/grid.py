#!/usr/bin/env python3
"""Run the vegetation index grid stage and write its output artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Optional, cast

import numpy as np
import rasterio

from agrivision.pipeline.grid.classify import classify_value_absolute, make_grid
from agrivision.pipeline.grid.io import (
    get_grid_settings,
    load_index_identity,
    save_categories_csv,
    save_cell_table_csv,
    save_grid_metadata,
)
from agrivision.pipeline.grid.render import save_grid_overlay


def run_grid_report() -> None:
    """Load the index raster, compute the grid, and write all grid artifacts."""
    resolved = get_grid_settings()
    ndvi_tif = cast(Path, resolved["ndvi_tif"])
    ndvi_meta_json = cast(Path, resolved["ndvi_meta_json"])
    grid_png = cast(Path, resolved["grid_png"])
    grid_table_csv = cast(Path, resolved["grid_table_csv"])
    grid_categories_csv = cast(Path, resolved["grid_categories_csv"])
    grid_meta_json = cast(Path, resolved["grid_meta_json"])
    grid_rows = cast(int, resolved["grid_rows"])
    grid_cols = cast(int, resolved["grid_cols"])
    poor_max_cfg = cast(float, resolved["poor_max_cfg"])
    medium_max_cfg = cast(float, resolved["medium_max_cfg"])

    print("[AgriVision] Grid report")
    print(f"  Raster source: {ndvi_tif}")
    print(f"  Grid: {grid_rows} rows x {grid_cols} cols")

    if not ndvi_tif.exists():
        raise FileNotFoundError(f"Index file not found: {ndvi_tif}")

    index_name, index_mode, source_dataset = load_index_identity(ndvi_meta_json)

    with rasterio.open(ndvi_tif) as src:
        arr = src.read(1).astype("float32")

    arr[~np.isfinite(arr)] = np.nan

    print("[Grid] First pass classification with configured thresholds:")
    print(f"       POOR_MAX={poor_max_cfg}, MEDIUM_MAX={medium_max_cfg}")

    def abs_classifier(v: Optional[float]) -> str:
        return classify_value_absolute(v, poor_max_cfg, medium_max_cfg)

    cells, row_edges, col_edges = make_grid(arr, abs_classifier, grid_rows, grid_cols)
    classes = {c["class"] for c in cells if c["mean_value"] is not None}
    print(f"[Grid] Classes found: {classes}")

    classification_mode = "fixed"
    poor_used = poor_max_cfg
    medium_used = medium_max_cfg

    if len(classes) <= 1 and classes and "no_data" not in classes:
        print("[Grid] All cells fell into one class; applying percentile fallback thresholds.")
        values = np.array(
            [c["mean_value"] for c in cells if c["mean_value"] is not None],
            dtype="float32",
        )
        q33, q66 = np.nanpercentile(values, [33, 66])
        print("[Grid] Fallback thresholds computed from cell means:")
        print(f"       33rd percentile: {q33:.4f}")
        print(f"       66th percentile: {q66:.4f}")

        classification_mode = "percentile_fallback"
        poor_used = float(q33)
        medium_used = float(q66)

        def dyn_classifier(v: Optional[float]) -> str:
            return classify_value_absolute(v, poor_used, medium_used)

        cells, row_edges, col_edges = make_grid(arr, dyn_classifier, grid_rows, grid_cols)

    save_grid_overlay(arr, cells, row_edges, col_edges, grid_png)
    save_cell_table_csv(cells, grid_table_csv, index_name=index_name, index_mode=index_mode)
    save_categories_csv(
        grid_categories_csv,
        poor_max=poor_used,
        medium_max=medium_used,
        index_name=index_name,
        index_mode=index_mode,
    )
    save_grid_metadata(
        grid_meta_json,
        index_name=index_name,
        index_mode=index_mode,
        source_dataset=source_dataset,
        classification_mode=classification_mode,
        poor_max_used=poor_used,
        medium_max_used=medium_used,
        grid_rows=grid_rows,
        grid_cols=grid_cols,
        poor_max_cfg=poor_max_cfg,
        medium_max_cfg=medium_max_cfg,
    )

    print("\n[AgriVision] Grid report complete.")
    print(f"  Overlay image : {grid_png}")
    print(f"  Cell table    : {grid_table_csv}")
    print(f"  Categories    : {grid_categories_csv}")
    print(f"  Grid metadata : {grid_meta_json}\n")


if __name__ == "__main__":
    run_grid_report()
