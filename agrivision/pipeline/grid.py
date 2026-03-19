#!/usr/bin/env python3
"""
agrivision.pipeline.grid

Create a grid over the vegetation index raster (ndvi.tif), classify each cell, and export:

  1. Grid overlay PNG
  2. CSV with one row per cell (cell ID, mean value, class)  [index-aware]
  3. CSV describing category thresholds used               [index-aware]
  4. grid_metadata.json describing classification mode + thresholds used

Files (stable names):
  output/ndvi/ndvi_grid_overlay.png
  output/ndvi/ndvi_grid_cells.csv
  output/ndvi/ndvi_grid_categories.csv
  output/ndvi/grid_metadata.json

Notes:
- The pipeline still uses ndvi.tif as a stable artifact name, even when the index is GNDVI-like or pseudo.
- Dynamic fallback is preserved: if absolute thresholds yield a single-class result, thresholds are recomputed from percentiles.
- CSV headers are updated to avoid misleading "NDVI" labeling while keeping backward compatibility (mean_ndvi retained).
"""

from __future__ import annotations

import csv
import json
import string
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, cast

import matplotlib.pyplot as plt
import numpy as np
import rasterio

from agrivision.utils.settings import get_project_root, load_config

COLOR_BY_CLASS = {
    "poor": "red",
    "medium": "yellow",
    "good": "lime",
    "no_data": "gray",
}


def _get_grid_settings() -> dict[str, object]:
    config = load_config()
    project_root = get_project_root()

    ndvi_dir = project_root / config["paths"]["ndvi_output"]
    ndvi_tif = ndvi_dir / "ndvi.tif"
    ndvi_meta_json = ndvi_dir / "metadata.json"
    grid_png = ndvi_dir / "ndvi_grid_overlay.png"
    grid_table_csv = ndvi_dir / "ndvi_grid_cells.csv"
    grid_categories_csv = ndvi_dir / "ndvi_grid_categories.csv"
    grid_meta_json = ndvi_dir / "grid_metadata.json"

    grid_rows = int(config["ndvi"]["grid_rows"])
    grid_cols = int(config["ndvi"]["grid_cols"])
    poor_max_cfg = float(config["ndvi"]["poor_max"])
    medium_max_cfg = float(config["ndvi"]["medium_max"])

    return {
        "ndvi_dir": ndvi_dir,
        "ndvi_tif": ndvi_tif,
        "ndvi_meta_json": ndvi_meta_json,
        "grid_png": grid_png,
        "grid_table_csv": grid_table_csv,
        "grid_categories_csv": grid_categories_csv,
        "grid_meta_json": grid_meta_json,
        "grid_rows": grid_rows,
        "grid_cols": grid_cols,
        "poor_max_cfg": poor_max_cfg,
        "medium_max_cfg": medium_max_cfg,
    }


# ---------------------------------------------------------------------
# Index metadata helpers
# ---------------------------------------------------------------------
def load_index_identity(ndvi_meta_json: Path) -> Tuple[str, str, str]:
    """
    Returns:
      (index_name, index_mode, source_dataset)

    Derived from output/ndvi/metadata.json written by agrivision.pipeline.ndvi.
    """
    if ndvi_meta_json.exists():
        try:
            with ndvi_meta_json.open("r", encoding="utf-8") as f:
                meta = json.load(f)
            idx = meta.get("index", {}) or {}
            src = meta.get("source", {}) or {}
            return (
                str(idx.get("index_name", "Vegetation Index")),
                str(idx.get("index_mode", "unknown")),
                str(src.get("dataset", "Unknown")),
            )
        except Exception:
            pass
    return "Vegetation Index", "unknown", "Unknown"


# ---------------------------------------------------------------------
# Grid utilities
# ---------------------------------------------------------------------
def row_letter(idx: int) -> str:
    """
    Convert row index (0-based) to Excel-like letters: 0 -> A, 1 -> B, ...
    Supports >26 rows with AA, AB, ...
    """
    letters = string.ascii_uppercase
    if idx < len(letters):
        return letters[idx]
    return letters[idx // len(letters) - 1] + letters[idx % len(letters)]


def classify_value_absolute(value: Optional[float], poor_max: float, medium_max: float) -> str:
    if value is None or not np.isfinite(value):
        return "no_data"
    if value < poor_max:
        return "poor"
    if value < medium_max:
        return "medium"
    return "good"


def make_grid(
    arr: np.ndarray, classifier, grid_rows: int, grid_cols: int
) -> Tuple[List[Dict[str, object]], np.ndarray, np.ndarray]:
    """
    Split the array into grid_rows x grid_cols cells and classify each.

    classifier is a function(mean_value) -> class_name
    """
    h, w = arr.shape

    row_edges = np.linspace(0, h, grid_rows + 1, dtype=int)
    col_edges = np.linspace(0, w, grid_cols + 1, dtype=int)

    cells: List[Dict[str, object]] = []

    for r in range(grid_rows):
        for c in range(grid_cols):
            r0, r1 = row_edges[r], row_edges[r + 1]
            c0, c1 = col_edges[c], col_edges[c + 1]

            patch = arr[r0:r1, c0:c1]
            mask = np.isfinite(patch)

            if not mask.any():
                mean_val: Optional[float] = None
            else:
                mean_val = float(patch[mask].mean())

            cls = classifier(mean_val)

            row_lbl = row_letter(r)
            col_lbl = c + 1
            cell_id = f"{row_lbl}{col_lbl}"

            cells.append(
                {
                    "row_idx": r,
                    "col_idx": c,
                    "row_label": row_lbl,
                    "col_label": col_lbl,
                    "cell_id": cell_id,
                    "mean_value": mean_val,  # canonical
                    "class": cls,
                    "r0": r0,
                    "r1": r1,
                    "c0": c0,
                    "c1": c1,
                }
            )

    return cells, row_edges, col_edges


# ---------------------------------------------------------------------
# Writers
# ---------------------------------------------------------------------
def save_grid_overlay(arr: np.ndarray, cells, row_edges, col_edges, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Visual normalization assumes index value in [-1, +1]. That holds for your ndvi.py output.
    arr_norm = (arr + 1.0) / 2.0
    arr_norm = np.clip(arr_norm, 0.0, 1.0)

    plt.figure(figsize=(8, 8))
    plt.imshow(arr_norm, cmap="YlGn", origin="upper")
    plt.axis("off")

    for x in col_edges:
        plt.axvline(x=x, color="black", linewidth=0.5, alpha=0.5)
    for y in row_edges:
        plt.axhline(y=y, color="black", linewidth=0.5, alpha=0.5)

    for cell in cells:
        r0, r1 = cell["r0"], cell["r1"]
        c0, c1 = cell["c0"], cell["c1"]
        y_center = (r0 + r1) / 2.0
        x_center = (c0 + c1) / 2.0

        label = cell["cell_id"]
        cls = cell["class"]
        color = COLOR_BY_CLASS.get(cls, "white")

        plt.text(
            x_center,
            y_center,
            label,
            color=color,
            fontsize=7,
            ha="center",
            va="center",
            fontweight="bold",
        )

    plt.tight_layout(pad=0)
    plt.savefig(out_path, dpi=300, bbox_inches="tight", pad_inches=0)
    plt.close()
    print(f"[OK] Grid overlay saved to {out_path}")


def save_cell_table_csv(
    cells: List[Dict[str, object]],
    out_path: Path,
    index_name: str,
    index_mode: str,
) -> None:
    """
    Index-aware grid cell CSV.

    Backward compatibility:
      - mean_ndvi column is retained (duplicate of mean_index).
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "cell_id",
        "row_label",
        "col_label",
        "mean_index",
        "mean_ndvi",   # backward compatibility
        "class",
        "index_name",
        "index_mode",
    ]

    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for cell in cells:
            mean_val = cell["mean_value"]
            mean_str = "" if mean_val is None else f"{float(mean_val):.4f}"

            writer.writerow(
                {
                    "cell_id": cell["cell_id"],
                    "row_label": cell["row_label"],
                    "col_label": cell["col_label"],
                    "mean_index": mean_str,
                    "mean_ndvi": mean_str,
                    "class": cell["class"],
                    "index_name": index_name,
                    "index_mode": index_mode,
                }
            )

    print(f"[OK] Cell table CSV saved to {out_path}")


def save_categories_csv(
    out_path: Path,
    poor_max: float,
    medium_max: float,
    index_name: str,
    index_mode: str,
) -> None:
    """
    Index-aware categories CSV.

    Schema:
      class, threshold_min, threshold_max, index_name, index_mode
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["class", "threshold_min", "threshold_max", "index_name", "index_mode"],
        )
        writer.writeheader()

        writer.writerow(
            {
                "class": "poor",
                "threshold_min": -1.0,
                "threshold_max": float(poor_max),
                "index_name": index_name,
                "index_mode": index_mode,
            }
        )
        writer.writerow(
            {
                "class": "medium",
                "threshold_min": float(poor_max),
                "threshold_max": float(medium_max),
                "index_name": index_name,
                "index_mode": index_mode,
            }
        )
        writer.writerow(
            {
                "class": "good",
                "threshold_min": float(medium_max),
                "threshold_max": 1.0,
                "index_name": index_name,
                "index_mode": index_mode,
            }
        )
        writer.writerow(
            {
                "class": "no_data",
                "threshold_min": "",
                "threshold_max": "",
                "index_name": index_name,
                "index_mode": index_mode,
            }
        )

    print(f"[OK] Categories CSV saved to {out_path}")


def save_grid_metadata(
    out_path: Path,
    index_name: str,
    index_mode: str,
    source_dataset: str,
    classification_mode: str,
    poor_max_used: float,
    medium_max_used: float,
    grid_rows: int,
    grid_cols: int,
    poor_max_cfg: float,
    medium_max_cfg: float,
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "generated_at_utc": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "index_name": index_name,
        "index_mode": index_mode,
        "source_dataset": source_dataset,
        "grid": {
            "rows": grid_rows,
            "cols": grid_cols,
        },
        "classification_mode": classification_mode,  # "fixed" or "percentile_fallback"
        "thresholds_used": {
            "poor_max": float(poor_max_used),
            "medium_max": float(medium_max_used),
        },
        "thresholds_configured": {
            "poor_max": float(poor_max_cfg),
            "medium_max": float(medium_max_cfg),
        },
    }

    with out_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print(f"[OK] Grid metadata saved to {out_path}")


# ---------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------
def run_grid_report() -> None:
    """
    High-level entry point: load index raster, compute grid, write outputs.
    Includes a dynamic fallback: if all cells are the same class using
    the configured absolute thresholds, recompute thresholds from percentiles.
    """
    resolved = _get_grid_settings()
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

    # First pass: absolute thresholds from config
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

    # Dynamic fallback if everything becomes one class (excluding no_data-only cases)
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
