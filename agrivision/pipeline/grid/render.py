"""Rendering helpers for grid visualization artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import matplotlib.pyplot as plt
import numpy as np

COLOR_BY_CLASS = {
    "poor": "red",
    "medium": "yellow",
    "good": "lime",
    "no_data": "gray",
}



def save_grid_overlay(
    arr: np.ndarray,
    cells: List[Dict[str, object]],
    row_edges: np.ndarray,
    col_edges: np.ndarray,
    out_path: Path,
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)

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
