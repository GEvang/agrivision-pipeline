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

from pathlib import Path
import csv
import string
import json
from datetime import datetime
from typing import List, Dict, Tuple, Optional

import matplotlib.pyplot as plt
import numpy as np
import rasterio

from agrivision.utils.settings import get_project_root, load_config


CONFIG = load_config()
PROJECT_ROOT = get_project_root()

NDVI_DIR = PROJECT_ROOT / CONFIG["paths"]["ndvi_output"]
NDVI_TIF = NDVI_DIR / "ndvi.tif"
NDVI_META_JSON = NDVI_DIR / "metadata.json"

GRID_PNG = NDVI_DIR / "ndvi_grid_overlay.png"
GRID_TABLE_CSV = NDVI_DIR / "ndvi_grid_cells.csv"
GRID_CATEGORIES_CSV = NDVI_DIR / "ndvi_grid_categories.csv"
GRID_META_JSON = NDVI_DIR / "grid_metadata.json"

# Grid + thresholds from config.yaml
GRID_ROWS = int(CONFIG["ndvi"]["grid_rows"])
GRID_COLS = int(CONFIG["ndvi"]["grid_cols"])
POOR_MAX_CFG = float(CONFIG["ndvi"]["poor_max"])
MEDIUM_MAX_CFG = float(CONFIG["ndvi"]["medium_max"])

COLOR_BY_CLASS = {
    "poor": "red",
    "medium": "yellow",
    "good": "lime",
    "no_data": "gray",
}


# ---------------------------------------------------------------------
# Index metadata helpers
# ---------------------------------------------------------------------
def load_index_identity() -> Tuple[str, str, str]:
    """
    Returns:
      (index_name, index_mode, source_dataset)

    Derived from output/ndvi/metadata.json written by agrivision.pipeline.ndvi.
    """
    if NDVI_META_JSON.exists():
        try:
            with NDVI_META_JSON.open("r", encoding="utf-8") as f:
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
    arr: np.ndarray, classifier
) -> Tuple[List[Dict[str, object]], np.ndarray, np.ndarray]:
    """
    Split the array into GRID_ROWS x GRID_COLS cells and classify each.

    classifier is a function(mean_value) -> class_name
    """
    h, w = arr.shape

    row_edges = np.linspace(0, h, GRID_ROWS + 1, dtype=int)
    col_edges = np.linspace(0, w, GRID_COLS + 1, dtype=int)

    cells: List[Dict[str, object]] = []

    for r in range(GRID_ROWS):
        for c in range(GRID_COLS):
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
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "generated_at_utc": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "index_name": index_name,
        "index_mode": index_mode,
        "source_dataset": source_dataset,
        "grid": {
            "rows": GRID_ROWS,
            "cols": GRID_COLS,
        },
        "classification_mode": classification_mode,  # "fixed" or "percentile_fallback"
        "thresholds_used": {
            "poor_max": float(poor_max_used),
            "medium_max": float(medium_max_used),
        },
        "thresholds_configured": {
            "poor_max": float(POOR_MAX_CFG),
            "medium_max": float(MEDIUM_MAX_CFG),
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
    print("[AgriVision] Grid report")
    print(f"  Raster source: {NDVI_TIF}")
    print(f"  Grid: {GRID_ROWS} rows x {GRID_COLS} cols")

    if not NDVI_TIF.exists():
        raise FileNotFoundError(f"Index file not found: {NDVI_TIF}")

    index_name, index_mode, source_dataset = load_index_identity()

    with rasterio.open(NDVI_TIF) as src:
        arr = src.read(1).astype("float32")

    arr[~np.isfinite(arr)] = np.nan

    # First pass: absolute thresholds from config
    print("[Grid] First pass classification with configured thresholds:")
    print(f"       POOR_MAX={POOR_MAX_CFG}, MEDIUM_MAX={MEDIUM_MAX_CFG}")

    def abs_classifier(v: Optional[float]) -> str:
        return classify_value_absolute(v, POOR_MAX_CFG, MEDIUM_MAX_CFG)

    cells, row_edges, col_edges = make_grid(arr, abs_classifier)

    classes = {c["class"] for c in cells if c["mean_value"] is not None}
    print(f"[Grid] Classes found: {classes}")

    classification_mode = "fixed"
    poor_used = POOR_MAX_CFG
    medium_used = MEDIUM_MAX_CFG

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

        cells, row_edges, col_edges = make_grid(arr, dyn_classifier)

    save_grid_overlay(arr, cells, row_edges, col_edges, GRID_PNG)
    save_cell_table_csv(cells, GRID_TABLE_CSV, index_name=index_name, index_mode=index_mode)
    save_categories_csv(
        GRID_CATEGORIES_CSV,
        poor_max=poor_used,
        medium_max=medium_used,
        index_name=index_name,
        index_mode=index_mode,
    )
    save_grid_metadata(
        GRID_META_JSON,
        index_name=index_name,
        index_mode=index_mode,
        source_dataset=source_dataset,
        classification_mode=classification_mode,
        poor_max_used=poor_used,
        medium_max_used=medium_used,
    )

    print("\n[AgriVision] Grid report complete.")
    print(f"  Overlay image : {GRID_PNG}")
    print(f"  Cell table    : {GRID_TABLE_CSV}")
    print(f"  Categories    : {GRID_CATEGORIES_CSV}")
    print(f"  Grid metadata : {GRID_META_JSON}\n")


if __name__ == "__main__":
    run_grid_report()
