"""Rendering helpers for grid visualization artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Tuple

import matplotlib

matplotlib.use("Agg", force=True)
import matplotlib.patheffects as path_effects
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from rasterio.enums import Resampling
from matplotlib.patches import Rectangle
from rasterio.warp import reproject

COLOR_BY_CLASS = {
    "poor": "#ef1d16",
    "medium": "#f5c400",
    "good": "#1fa447",
    "no_data": "#8a8f98",
}
TEXT_BY_CLASS = {
    "poor": "#ef1d16",
    "medium": "#f5c400",
    "good": "#00e53b",
    "no_data": "#8a8f98",
}

MAX_DISPLAY_SIDE = 2500


def _display_shape(shape: Tuple[int, int]) -> Tuple[int, int, float]:
    height, width = shape
    scale = min(1.0, MAX_DISPLAY_SIDE / float(max(height, width)))
    return max(1, int(round(height * scale))), max(1, int(round(width * scale))), scale


def _normalize_rgb(bands: np.ndarray) -> np.ndarray:
    image = bands.astype("float32")
    if image.shape[0] == 1:
        image = np.repeat(image, 3, axis=0)
    image = image[:3]

    out = np.zeros_like(image, dtype="float32")
    for idx, band in enumerate(image):
        finite = np.isfinite(band)
        if not np.any(finite):
            continue

        low, high = np.nanpercentile(band[finite], [2, 98])
        if high <= low:
            high = float(np.nanmax(band[finite]))
            low = float(np.nanmin(band[finite]))
        if high <= low:
            continue

        out[idx] = np.clip((band - low) / (high - low), 0.0, 1.0)

    return np.moveaxis(out, 0, -1)


def _read_rgb_background(
    background_path: Path,
    shape: Tuple[int, int],
    reference_transform: Any | None = None,
    reference_crs: Any | None = None,
) -> Tuple[np.ndarray, float] | None:
    if not background_path.exists():
        return None

    display_height, display_width, scale = _display_shape(shape)
    with rasterio.open(background_path) as src:
        indexes = [idx for idx in (1, 2, 3) if idx <= src.count]
        if not indexes:
            return None

        if reference_transform is not None and reference_crs is not None and src.crs is not None:
            dst_transform = reference_transform * reference_transform.scale(1 / scale, 1 / scale)
            bands = np.zeros((len(indexes), display_height, display_width), dtype="float32")
            for out_idx, band_idx in enumerate(indexes):
                reproject(
                    source=rasterio.band(src, band_idx),
                    destination=bands[out_idx],
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=dst_transform,
                    dst_crs=reference_crs,
                    resampling=Resampling.bilinear,
                    dst_nodata=0,
                )
        else:
            bands = src.read(indexes, out_shape=(len(indexes), display_height, display_width))

    return _normalize_rgb(bands), scale


def _index_background(arr: np.ndarray) -> Tuple[np.ndarray, float]:
    display_height, display_width, scale = _display_shape(arr.shape)
    row_idx = np.linspace(0, arr.shape[0] - 1, display_height).astype(int)
    col_idx = np.linspace(0, arr.shape[1] - 1, display_width).astype(int)
    arr_display = arr[np.ix_(row_idx, col_idx)]
    arr_norm = (arr_display + 1.0) / 2.0
    return np.clip(arr_norm, 0.0, 1.0), scale

def save_grid_overlay(
    arr: np.ndarray,
    cells: List[Dict[str, object]],
    row_edges: np.ndarray,
    col_edges: np.ndarray,
    out_path: Path,
    background_path: Path | None = None,
    reference_transform: Any | None = None,
    reference_crs: Any | None = None,
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)

    rgb_background = (
        _read_rgb_background(
            background_path,
            arr.shape,
            reference_transform=reference_transform,
            reference_crs=reference_crs,
        )
        if background_path is not None
        else None
    )

    plt.figure(figsize=(8, 8))
    if rgb_background is not None:
        image, scale = rgb_background
        plt.imshow(image, origin="upper")
    else:
        image, scale = _index_background(arr)
        plt.imshow(image, cmap="YlGn", origin="upper")

    plt.axis("off")

    ax = plt.gca()
    for cell in cells:
        cls = cell["class"]
        if cls == "no_data":
            continue

        r0, r1 = cell["r0"], cell["r1"]
        c0, c1 = cell["c0"], cell["c1"]
        x = c0 * scale
        y = r0 * scale
        width = max((c1 - c0) * scale, 1)
        height = max((r1 - r0) * scale, 1)
        y_center = ((r0 + r1) / 2.0) * scale
        x_center = ((c0 + c1) / 2.0) * scale
        label = cell["cell_id"]
        fill_color = COLOR_BY_CLASS.get(cls, "#ffffff")
        text_color = TEXT_BY_CLASS.get(cls, "#ffffff")

        ax.add_patch(
            Rectangle(
                (x, y),
                width,
                height,
                facecolor=fill_color,
                edgecolor="white",
                linewidth=0.7,
                alpha=0.48,
                zorder=2,
            )
        )

        text = plt.text(
            x_center,
            y_center,
            label,
            color=text_color,
            fontsize=7,
            ha="center",
            va="center",
            fontweight="bold",
            zorder=4,
        )
        text.set_path_effects([path_effects.withStroke(linewidth=1.2, foreground="black", alpha=0.55)])

    for x in col_edges:
        plt.axvline(x=x * scale, color="white", linewidth=0.45, alpha=0.65, zorder=3)
    for y in row_edges:
        plt.axhline(y=y * scale, color="white", linewidth=0.45, alpha=0.65, zorder=3)

    plt.tight_layout(pad=0)
    plt.savefig(out_path, dpi=300, bbox_inches="tight", pad_inches=0)
    plt.close()
    print(f"[OK] Grid overlay saved to {out_path}")
