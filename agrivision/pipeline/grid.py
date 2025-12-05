#!/usr/bin/env python3
"""
agrivision.pipeline.grid

Create a grid over the NDVI raster, classify each cell, and export:

  1. Grid overlay PNG
  2. CSV with one row per cell (cell ID, mean NDVI, class)
  3. CSV with columns poor/medium/good/no_data (lists of cells)
"""

from pathlib import Path
import csv
import string
from typing import List, Dict, Tuple

import matplotlib.pyplot as plt
import numpy as np
import rasterio

from agrivision.utils.settings import get_project_root, load_config


CONFIG = load_config()
PROJECT_ROOT = get_project_root()

NDVI_DIR = PROJECT_ROOT / CONFIG["paths"]["ndvi_output"]
NDVI_TIF = NDVI_DIR / "ndvi.tif"

GRID_PNG = NDVI_DIR / "ndvi_grid_overlay.png"
GRID_TABLE_CSV = NDVI_DIR / "ndvi_grid_cells.csv"
GRID_CATEGORIES_CSV = NDVI_DIR / "ndvi_grid_categories.csv"

# Grid + thresholds from config.yaml
GRID_ROWS = int(CONFIG["ndvi"]["grid_rows"])
GRID_COLS = int(CONFIG["ndvi"]["grid_cols"])
POOR_MAX = float(CONFIG["ndvi"]["poor_max"])
MEDIUM_MAX = float(CONFIG["ndvi"]["medium_max"])

COLOR_BY_CLASS = {
    "poor": "red",
    "medium": "yellow",
    "good": "lime",
    "no_data": "gray",
}


def row_letter(idx: int) -> str:
    """
    Convert row index (0-based) to Excel-like letter: 0 -> A, 1 -> B, ...
    Supports >26 rows with AA, AB, ...
    """
    letters = string.ascii_uppercase
    if idx < len(letters):
        return letters[idx]
    return letters[idx // len(letters) - 1] + letters[idx % len(letters)]


def classify_ndvi_absolute(value: float | None) -> str:
    if value is None or not np.isfinite(value):
        return "no_data"
    if value < POOR_MAX:
        return "poor"
    if value < MEDIUM_MAX:
        return "medium"
    return "good"


def classify_ndvi_dynamic(value: float | None, t1: float, t2: float) -> str:
    """
    Dynamic classification using thresholds t1, t2 (e.g. 33rd and 66th percentile).
    """
    if value is None or not np.isfinite(value):
        return "no_data"
    if value < t1:
        return "poor"
    if value < t2:
        return "medium"
    return "good"


def make_grid(
    ndvi: np.ndarray, classifier
) -> Tuple[List[Dict[str, object]], np.ndarray, np.ndarray]:
    """
    Split the NDVI array into GRID_ROWS x GRID_COLS cells and classify each.

    classifier is a function(mean_value) -> class_name
    """
    h, w = ndvi.shape

    row_edges = np.linspace(0, h, GRID_ROWS + 1, dtype=int)
    col_edges = np.linspace(0, w, GRID_COLS + 1, dtype=int)

    cells: List[Dict[str, object]] = []

    for r in range(GRID_ROWS):
        for c in range(GRID_COLS):
            r0, r1 = row_edges[r], row_edges[r + 1]
            c0, c1 = col_edges[c], col_edges[c + 1]

            patch = ndvi[r0:r1, c0:c1]
            mask = np.isfinite(patch)

            if not mask.any():
                mean_val = None
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
                    "mean_ndvi": mean_val,
                    "class": cls,
                    "r0": r0,
                    "r1": r1,
                    "c0": c0,
                    "c1": c1,
                }
            )

    return cells, row_edges, col_edges


def save_grid_overlay(ndvi: np.ndarray, cells, row_edges, col_edges, out_path: Path):
    out_path.parent.mkdir(parents=True, exist_ok=True)

    ndvi_norm = (ndvi + 1.0) / 2.0
    ndvi_norm = np.clip(ndvi_norm, 0.0, 1.0)

    plt.figure(figsize=(8, 8))
    plt.imshow(ndvi_norm, cmap="YlGn", origin="upper")
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


def save_cell_table_csv(cells, out_path: Path):
    out_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = ["cell_id", "row_label", "col_label", "mean_ndvi", "class"]
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for cell in cells:
            mean_val = cell["mean_ndvi"]
            writer.writerow(
                {
                    "cell_id": cell["cell_id"],
                    "row_label": cell["row_label"],
                    "col_label": cell["col_label"],
                    "mean_ndvi": ""
                    if mean_val is None
                    else f"{mean_val:.4f}",
                    "class": cell["class"],
                }
            )

    print(f"[OK] Cell table CSV saved to {out_path}")


def save_categories_csv(cells, out_path: Path):
    out_path.parent.mkdir(parents=True, exist_ok=True)

    buckets = {
        "poor": [],
        "medium": [],
        "good": [],
        "no_data": [],
    }

    for cell in cells:
        buckets[cell["class"]].append(cell["cell_id"])

    max_len = max(len(v) for v in buckets.values()) if buckets else 0

    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["poor", "medium", "good", "no_data"])

        for i in range(max_len):
            row = [
                buckets["poor"][i] if i < len(buckets["poor"]) else "",
                buckets["medium"][i] if i < len(buckets["medium"]) else "",
                buckets["good"][i] if i < len(buckets["good"]) else "",
                buckets["no_data"][i] if i < len(buckets["no_data"]) else "",
            ]
            writer.writerow(row)

    print(f"[OK] Category CSV saved to {out_path}")


def run_grid_report() -> None:
    """
    High-level entry point: load NDVI, compute grid, write outputs.
    Includes a dynamic fallback: if all cells are the same class using
    the absolute thresholds, we recompute thresholds based on percentiles.
    """
    print(f"[AgriVision] NDVI grid report")
    print(f"  NDVI source: {NDVI_TIF}")
    print(f"  Grid: {GRID_ROWS} rows x {GRID_COLS} cols")

    if not NDVI_TIF.exists():
        raise FileNotFoundError(f"NDVI file not found: {NDVI_TIF}")

    with rasterio.open(NDVI_TIF) as src:
        ndvi = src.read(1).astype("float32")

    ndvi[~np.isfinite(ndvi)] = np.nan

    # First pass: absolute thresholds from config
    print(f"[Grid] First pass classification with absolute thresholds:")
    print(f"       POOR_MAX={POOR_MAX}, MEDIUM_MAX={MEDIUM_MAX}")
    cells, row_edges, col_edges = make_grid(ndvi, classify_ndvi_absolute)

    classes = {c["class"] for c in cells if c["mean_ndvi"] is not None}
    print(f"[Grid] Classes found: {classes}")

    # If everything is a single class (e.g. all 'poor'), do a dynamic re-class
    if len(classes) <= 1 and classes and "no_data" not in classes:
        print("[Grid] All cells fell into one class, applying dynamic thresholds.")
        # collect all finite mean values
        values = np.array(
            [c["mean_ndvi"] for c in cells if c["mean_ndvi"] is not None],
            dtype="float32",
        )
        q33, q66 = np.nanpercentile(values, [33, 66])
        print(f"[Grid] Dynamic thresholds based on cell means:")
        print(f"       33rd percentile: {q33:.4f}")
        print(f"       66th percentile: {q66:.4f}")

        cells, row_edges, col_edges = make_grid(
            ndvi, lambda v: classify_ndvi_dynamic(v, q33, q66)
        )

    save_grid_overlay(ndvi, cells, row_edges, col_edges, GRID_PNG)
    save_cell_table_csv(cells, GRID_TABLE_CSV)
    save_categories_csv(cells, GRID_CATEGORIES_CSV)

    print("\n[AgriVision] NDVI grid report complete.")
    print(f"  Overlay image : {GRID_PNG}")
    print(f"  Cell table    : {GRID_TABLE_CSV}")
    print(f"  Categories    : {GRID_CATEGORIES_CSV}\n")


if __name__ == "__main__":
    run_grid_report()

