"""Grid classification helpers for vegetation index rasters."""

from __future__ import annotations

import string
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np

CellRecord = Dict[str, object]
Classifier = Callable[[Optional[float]], str]


def row_letter(idx: int) -> str:
    """Convert a zero-based row index to Excel-like row labels."""
    letters = string.ascii_uppercase
    if idx < len(letters):
        return letters[idx]
    return letters[idx // len(letters) - 1] + letters[idx % len(letters)]



def classify_value_absolute(
    value: Optional[float], poor_max: float, medium_max: float
) -> str:
    if value is None or not np.isfinite(value):
        return "no_data"
    if value < poor_max:
        return "poor"
    if value < medium_max:
        return "medium"
    return "good"



def make_grid(
    arr: np.ndarray,
    classifier: Classifier,
    grid_rows: int,
    grid_cols: int,
    min_valid_fraction: float = 0.0,
) -> Tuple[List[CellRecord], np.ndarray, np.ndarray]:
    """Split an array into grid cells and classify each cell by its mean value."""
    h, w = arr.shape

    row_edges = np.linspace(0, h, grid_rows + 1, dtype=int)
    col_edges = np.linspace(0, w, grid_cols + 1, dtype=int)

    cells: List[CellRecord] = []

    for r in range(grid_rows):
        for c in range(grid_cols):
            r0, r1 = row_edges[r], row_edges[r + 1]
            c0, c1 = col_edges[c], col_edges[c + 1]

            patch = arr[r0:r1, c0:c1]
            mask = np.isfinite(patch)
            valid_fraction = float(mask.mean()) if patch.size else 0.0

            if not mask.any() or valid_fraction < min_valid_fraction:
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
                    "mean_value": mean_val,
                    "valid_fraction": valid_fraction,
                    "class": cls,
                    "r0": r0,
                    "r1": r1,
                    "c0": c0,
                    "c1": c1,
                }
            )

    return cells, row_edges, col_edges
