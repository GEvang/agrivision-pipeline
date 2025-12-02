#!/usr/bin/env python3
"""
ndvi_grid_report.py

Create a grid over the NDVI raster, classify each cell, and export:

  1. A grid overlay PNG (NDVI background + grid + colored labels)
  2. A CSV with one row per cell (cell ID, mean NDVI, class)
  3. A CSV with columns poor/medium/good/no_data for easy viewing in Excel

Usage (from project root):

    source venv/bin/activate
    python3 scripts/ndvi_grid_report.py

You can tweak GRID_ROWS, GRID_COLS and thresholds below.
"""

from pathlib import Path
import csv
import string

import numpy as np
import rasterio
import matplotlib.pyplot as plt


# ---------- CONFIG ----------

BASE_DIR = Path(__file__).resolve().parent.parent

NDVI_TIF = BASE_DIR / "output" / "ndvi" / "ndvi.tif"

# Where to save outputs
GRID_PNG = BASE_DIR / "output" / "ndvi" / "ndvi_grid_overlay.png"
GRID_TABLE_CSV = BASE_DIR / "output" / "ndvi" / "ndvi_grid_cells.csv"
GRID_CATEGORIES_CSV = BASE_DIR / "output" / "ndvi" / "ndvi_grid_categories.csv"

# Grid resolution (rows = letters, columns = numbers)
GRID_ROWS = 17  # A..Q
GRID_COLS = 17  # 1..17

# NDVI classification thresholds
#   NDVI < POOR_MAX        -> "poor"
#   POOR_MAX..MEDIUM_MAX   -> "medium"
#   MEDIUM_MAX..1          -> "good"
POOR_MAX = 0.3
MEDIUM_MAX = 0.6

# Colors for labels
COLOR_BY_CLASS = {
    "poor": "red",
    "medium": "yellow",
    "good": "lime",
    "no_data": "gray",
}

# ----------------------------


def classify_ndvi(value: float | None) -> str:
    if value is None or np.isnan(value):
        return "no_data"
    if value < POOR_MAX:
        return "poor"
    if value < MEDIUM_MAX:
        return "medium"
    return "good"


def row_letter(idx: int) -> str:
    # 0 -> A, 1 -> B, ...
    letters = string.ascii_uppercase
    if idx < len(letters):
        return letters[idx]
    # fallback if someone sets GRID_ROWS > 26
    return letters[idx // len(letters) - 1] + letters[idx % len(letters)]


def make_grid(ndvi: np.ndarray):
    """
    Split the NDVI array into GRID_ROWS x GRID_COLS cells
    and compute mean NDVI + class for each.

    Returns:
        cells: list of dicts with keys:
            'row_idx', 'col_idx', 'row_label', 'col_label',
            'cell_id', 'mean_ndvi', 'class'
    """
    h, w = ndvi.shape

    row_edges = np.linspace(0, h, GRID_ROWS + 1, dtype=int)
    col_edges = np.linspace(0, w, GRID_COLS + 1, dtype=int)

    cells = []

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

            cls = classify_ndvi(mean_val)

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
    """
    Create a PNG with NDVI background, grid lines and colored cell labels.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)

    h, w = ndvi.shape

    # Normalize NDVI to [0, 1] for visualization
    ndvi_norm = (ndvi + 1.0) / 2.0
    ndvi_norm = np.clip(ndvi_norm, 0.0, 1.0)

    plt.figure(figsize=(8, 8))
    plt.imshow(ndvi_norm, cmap="YlGn", origin="upper")
    plt.axis("off")

    # Grid lines
    for x in col_edges:
        plt.axvline(x=x, color="black", linewidth=0.5, alpha=0.5)
    for y in row_edges:
        plt.axhline(y=y, color="black", linewidth=0.5, alpha=0.5)

    # Labels
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
    """
    Save a CSV with one row per cell:
        cell_id, row_label, col_label, mean_ndvi, class
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = ["cell_id", "row_label", "col_label", "mean_ndvi", "class"]
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for cell in cells:
            writer.writerow(
                {
                    "cell_id": cell["cell_id"],
                    "row_label": cell["row_label"],
                    "col_label": cell["col_label"],
                    "mean_ndvi": "" if cell["mean_ndvi"] is None else f"{cell['mean_ndvi']:.4f}",
                    "class": cell["class"],
                }
            )

    print(f"[OK] Cell table CSV saved to {out_path}")


def save_categories_csv(cells, out_path: Path):
    """
    Save a CSV with columns: poor, medium, good, no_data
    Each row lists cell IDs for that category (like the screenshot example).
    """
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


def main():
    print(f"[AgriVision] NDVI grid report")
    print(f"  NDVI source: {NDVI_TIF}")
    print(f"  Grid: {GRID_ROWS} rows x {GRID_COLS} cols")

    if not NDVI_TIF.exists():
        raise FileNotFoundError(f"NDVI file not found: {NDVI_TIF}")

    with rasterio.open(NDVI_TIF) as src:
        ndvi = src.read(1).astype("float32")

    ndvi[~np.isfinite(ndvi)] = np.nan

    cells, row_edges, col_edges = make_grid(ndvi)

    save_grid_overlay(ndvi, cells, row_edges, col_edges, GRID_PNG)
    save_cell_table_csv(cells, GRID_TABLE_CSV)
    save_categories_csv(cells, GRID_CATEGORIES_CSV)

    print("\n[AgriVision] NDVI grid report complete.")
    print(f"  Overlay image : {GRID_PNG}")
    print(f"  Cell table    : {GRID_TABLE_CSV}")
    print(f"  Categories    : {GRID_CATEGORIES_CSV}")
    print("\nYou can open the CSV files in Excel or LibreOffice.")


if __name__ == "__main__":
    main()

