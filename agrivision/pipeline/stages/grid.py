#!/usr/bin/env python3
"""Run the vegetation index grid stage and write its output artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional, cast

import numpy as np
import rasterio
from rasterio.enums import Resampling

from agrivision.pipeline.grid.classify import classify_value_absolute, make_grid
from agrivision.pipeline.grid.io import (
    get_grid_settings,
    load_index_identity,
    save_categories_csv,
    save_cell_table_csv,
    save_grid_metadata,
)
from agrivision.pipeline.grid.render import save_grid_overlay
from agrivision.pipeline.stages.vegetation_index import save_png


def _save_masked_index_png(arr: np.ndarray, out_png: Path, title: str, out_dir: Path) -> None:
    max_edge = 1800
    scale = min(1.0, max_edge / float(max(arr.shape)))
    if scale < 1.0:
        row_idx = np.linspace(0, arr.shape[0] - 1, max(1, int(arr.shape[0] * scale))).astype(int)
        col_idx = np.linspace(0, arr.shape[1] - 1, max(1, int(arr.shape[1] * scale))).astype(int)
        preview = arr[np.ix_(row_idx, col_idx)]
    else:
        preview = arr
    save_png(preview, out_png, title=title, out_dir=out_dir)


def _preview_array(arr: np.ndarray, max_edge: int = 3000) -> np.ndarray:
    scale = min(1.0, max_edge / float(max(arr.shape)))
    if scale >= 1.0:
        return arr
    row_idx = np.linspace(0, arr.shape[0] - 1, max(1, int(arr.shape[0] * scale))).astype(int)
    col_idx = np.linspace(0, arr.shape[1] - 1, max(1, int(arr.shape[1] * scale))).astype(int)
    return arr[np.ix_(row_idx, col_idx)]


def _resample_array_to_shape(arr: np.ndarray, shape: tuple[int, int]) -> np.ndarray:
    row_idx = np.linspace(0, arr.shape[0] - 1, shape[0]).astype(int)
    col_idx = np.linspace(0, arr.shape[1] - 1, shape[1]).astype(int)
    return arr[np.ix_(row_idx, col_idx)]


def _analysis_mask_from_rgb(rgb_path: Path, shape: tuple[int, int], out_png: Path) -> np.ndarray | None:
    """Build a pixel-space mask that removes obvious hard surfaces from RGB."""
    if not rgb_path.exists():
        return None
    full_height, full_width = shape
    scale = min(1.0, 3000 / float(max(shape)))
    height = max(1, int(full_height * scale))
    width = max(1, int(full_width * scale))
    try:
        with rasterio.open(rgb_path) as src:
            if src.count < 3:
                return None
            rgb = src.read(
                [1, 2, 3],
                out_shape=(3, height, width),
                resampling=Resampling.bilinear,
            ).astype("float32")
    except (OSError, rasterio.errors.RasterioError):
        return None

    red, green, blue = rgb
    total = red + green + blue
    finite = np.isfinite(total)
    brightness = total / 3.0
    max_channel = np.maximum.reduce([red, green, blue])
    min_channel = np.minimum.reduce([red, green, blue])
    saturation = (max_channel - min_channel) / (max_channel + 1e-6)
    green_ratio = green / (total + 1e-6)
    red_ratio = red / (total + 1e-6)

    bright_gray_surface = (brightness > 185.0) & (saturation < 0.13)
    red_roof_surface = (red_ratio > 0.44) & (green_ratio < 0.34)
    shadow_or_black_surface = brightness < 18.0
    mask = (
        finite
        & (brightness < 235.0)
        & (saturation > 0.035)
        & ~bright_gray_surface
        & ~red_roof_surface
        & ~shadow_or_black_surface
    )

    out_png.parent.mkdir(parents=True, exist_ok=True)
    plt_mask = mask.astype("uint8") * 255
    import matplotlib.pyplot as plt

    plt.figure(figsize=(8, 8))
    plt.imshow(plt_mask, cmap="gray", vmin=0, vmax=255)
    plt.axis("off")
    plt.tight_layout(pad=0)
    plt.savefig(out_png, dpi=220, bbox_inches="tight", pad_inches=0)
    plt.close()
    print(f"[Grid] Analysis mask saved: {out_png}")
    print(f"[Grid] Analysis mask retained {float(mask.mean() * 100.0):.1f}% of preview pixels.")
    return mask


def run_grid_report(
    workspace_root: Path | None = None,
    config: dict[str, Any] | None = None,
) -> None:
    """Load the index raster, compute the grid, and write all grid artifacts."""
    resolved = get_grid_settings(workspace_root=workspace_root, config=config)
    ndvi_tif = cast(Path, resolved["ndvi_tif"])
    ndvi_meta_json = cast(Path, resolved["ndvi_meta_json"])
    ortho_rgb = cast(Path, resolved["ortho_rgb"])
    grid_png = cast(Path, resolved["grid_png"])
    analysis_mask_png = cast(Path, resolved["analysis_mask_png"])
    grid_table_csv = cast(Path, resolved["grid_table_csv"])
    grid_categories_csv = cast(Path, resolved["grid_categories_csv"])
    grid_meta_json = cast(Path, resolved["grid_meta_json"])
    grid_rows = cast(int, resolved["grid_rows"])
    grid_cols = cast(int, resolved["grid_cols"])
    poor_max_cfg = cast(float, resolved["poor_max_cfg"])
    medium_max_cfg = cast(float, resolved["medium_max_cfg"])
    threshold_mode = cast(str, resolved["threshold_mode"]).strip().lower()
    calibration_percentiles = cast(list[float], resolved["calibration_percentiles"])
    min_cell_valid_fraction = cast(float, resolved["min_cell_valid_fraction"])
    if len(calibration_percentiles) < 2:
        calibration_percentiles = [33, 66]

    print("[AgriVision] Grid report")
    print(f"  Raster source: {ndvi_tif}")
    print(f"  Grid: {grid_rows} rows x {grid_cols} cols")

    if not ndvi_tif.exists():
        raise FileNotFoundError(f"Index file not found: {ndvi_tif}")

    index_name, index_mode, source_dataset = load_index_identity(ndvi_meta_json)

    with rasterio.open(ndvi_tif) as src:
        arr = src.read(1).astype("float32")

    arr[~np.isfinite(arr)] = np.nan
    analysis_arr = arr
    analysis_mask = _analysis_mask_from_rgb(ortho_rgb, arr.shape, analysis_mask_png)
    if analysis_mask is not None:
        analysis_arr = _resample_array_to_shape(arr, analysis_mask.shape)
        analysis_arr = analysis_arr.copy()
        analysis_arr[~analysis_mask] = np.nan
        _save_masked_index_png(analysis_arr, ndvi_tif.with_name("ndvi_color.png"), title=index_name, out_dir=ndvi_tif.parent)

    print("[Grid] First pass classification with configured thresholds:")
    print(f"       POOR_MAX={poor_max_cfg}, MEDIUM_MAX={medium_max_cfg}")
    print(f"       THRESHOLD_MODE={threshold_mode}")
    print(f"       MIN_CELL_VALID_FRACTION={min_cell_valid_fraction}")

    def abs_classifier(v: Optional[float]) -> str:
        return classify_value_absolute(v, poor_max_cfg, medium_max_cfg)

    cells, row_edges, col_edges = make_grid(
        analysis_arr,
        abs_classifier,
        grid_rows,
        grid_cols,
        min_valid_fraction=min_cell_valid_fraction,
    )
    classes = {c["class"] for c in cells if c["mean_value"] is not None}
    print(f"[Grid] Classes found: {classes}")

    classification_mode = "fixed"
    poor_used = poor_max_cfg
    medium_used = medium_max_cfg

    if threshold_mode == "percentile":
        print("[Grid] Applying calibrated percentile thresholds from cell means.")
        values = np.array(
            [c["mean_value"] for c in cells if c["mean_value"] is not None],
            dtype="float32",
        )
        if values.size < 2:
            raise RuntimeError("[Grid] Not enough valid grid cells to calibrate thresholds.")

        p_low = float(calibration_percentiles[0])
        p_high = float(calibration_percentiles[1])
        q33, q66 = np.nanpercentile(values, [p_low, p_high])
        print("[Grid] Calibrated thresholds computed from cell means:")
        print(f"       {p_low:g} percentile: {q33:.4f}")
        print(f"       {p_high:g} percentile: {q66:.4f}")

        classification_mode = "percentile_calibrated"
        poor_used = float(q33)
        medium_used = float(q66)

        def dyn_classifier(v: Optional[float]) -> str:
            return classify_value_absolute(v, poor_used, medium_used)

        cells, row_edges, col_edges = make_grid(
            analysis_arr,
            dyn_classifier,
            grid_rows,
            grid_cols,
            min_valid_fraction=min_cell_valid_fraction,
        )
    elif len(classes) <= 1 and classes and "no_data" not in classes:
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

        cells, row_edges, col_edges = make_grid(
            analysis_arr,
            dyn_classifier,
            grid_rows,
            grid_cols,
            min_valid_fraction=min_cell_valid_fraction,
        )

    save_grid_overlay(analysis_arr, cells, row_edges, col_edges, grid_png, background_path=ortho_rgb)
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
        threshold_mode=threshold_mode,
        calibration_percentiles=[float(calibration_percentiles[0]), float(calibration_percentiles[1])],
        min_cell_valid_fraction=min_cell_valid_fraction,
    )

    print("\n[AgriVision] Grid report complete.")
    print(f"  Overlay image : {grid_png}")
    print(f"  Cell table    : {grid_table_csv}")
    print(f"  Categories    : {grid_categories_csv}")
    print(f"  Grid metadata : {grid_meta_json}\n")


if __name__ == "__main__":
    run_grid_report()
