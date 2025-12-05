#!/usr/bin/env python3
"""
agrivision.pipeline.ndvi

Compute NDVI from the ODM orthophoto and save:

  - GeoTIFF:  output/ndvi/ndvi.tif
  - Color PNG: output/ndvi/ndvi_color.png (with legend, percentile-stretched)
"""

from pathlib import Path
from typing import Dict

import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np
import rasterio

from agrivision.utils.settings import get_project_root, load_config


CONFIG = load_config()
PROJECT_ROOT = get_project_root()

# Paths from config.yaml
ODM_PROJECT_ROOT = PROJECT_ROOT / CONFIG["paths"]["odm_project_root"]
NDVI_DIR = PROJECT_ROOT / CONFIG["paths"]["ndvi_output"]

ORTHO_PATH = ODM_PROJECT_ROOT / "project" / "odm_orthophoto" / "odm_orthophoto.tif"
NDVI_TIF_OUT = NDVI_DIR / "ndvi.tif"
NDVI_PNG_OUT = NDVI_DIR / "ndvi_color.png"


# Camera profiles (band indices are 1-based)
CAMERA_PROFILES: Dict[str, Dict[str, int]] = {
    "sample_mapir_unknown": {"red": 1, "nir": 2},
    # add more profiles if needed
}


def compute_ndvi_array(red: np.ndarray, nir: np.ndarray) -> np.ndarray:
    """Compute NDVI = (NIR - RED) / (NIR + RED)."""
    red = red.astype("float32")
    nir = nir.astype("float32")

    num = nir - red
    den = nir + red

    ndvi = np.zeros_like(num, dtype="float32")
    mask = den != 0
    ndvi[mask] = num[mask] / den[mask]
    ndvi[~mask] = np.nan
    return ndvi


def save_ndvi_geotiff(template_src: rasterio.DatasetReader, ndvi: np.ndarray, out_path: Path) -> None:
    """Save NDVI array to GeoTIFF using georeferencing from template_src."""
    out_path.parent.mkdir(parents=True, exist_ok=True)

    profile = template_src.profile.copy()
    profile.update(dtype="float32", count=1, nodata=np.nan)

    with rasterio.open(out_path, "w", **profile) as dst:
        dst.write(ndvi, 1)

    print(f"[OK] NDVI GeoTIFF saved to {out_path}")


def save_ndvi_png(ndvi: np.ndarray, out_path: Path) -> None:
    """
    Save NDVI as a PNG using a classic Red→Yellow→Green palette
    and dynamic contrast stretching based on the NDVI distribution.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Work on a copy
    ndvi_plot = ndvi.astype("float32")

    # Mask non-finite values
    finite_mask = np.isfinite(ndvi_plot)
    if not finite_mask.any():
        print("[WARN] NDVI image has no finite values; skipping PNG export.")
        return

    values = ndvi_plot[finite_mask]

    # Compute robust min/max from percentiles to enhance contrast
    vmin, vmax = np.nanpercentile(values, [2, 98])
    if vmin == vmax:
        # fallback if all values identical
        vmin, vmax = float(values.min()), float(values.max())
        if vmin == vmax:
            # truly constant NDVI; just use a small band around the value
            vmin = vmin - 0.05
            vmax = vmax + 0.05

    print(f"[NDVI] Visualization range (percentiles): vmin={vmin:.3f}, vmax={vmax:.3f}")

    # Clip to that range for display
    ndvi_plot = np.clip(ndvi_plot, vmin, vmax)

    # Classic NDVI colormap: red (low) → yellow → green (high)
    cmap = plt.get_cmap("RdYlGn")

    # Make NaNs show as dark gray
    cmap = cmap.copy()
    cmap.set_bad(color="#3a3a3a")

    plt.figure(figsize=(8, 8))
    im = plt.imshow(ndvi_plot, cmap=cmap, vmin=vmin, vmax=vmax)
    plt.axis("off")

    # Colorbar legend
    cbar = plt.colorbar(im, shrink=0.8)
    cbar.set_label("NDVI", rotation=270, labelpad=15)

    plt.tight_layout()
    plt.savefig(out_path, dpi=300, bbox_inches="tight", pad_inches=0.1)
    plt.close()

    print(f"[OK] NDVI COLOR PNG saved to {out_path}")


def run_ndvi(camera_name: str = "sample_mapir_unknown") -> None:
    """High-level entry point for NDVI computation."""
    camera = CAMERA_PROFILES.get(camera_name)
    if camera is None:
        known = ", ".join(CAMERA_PROFILES.keys())
        raise ValueError(f"Unknown camera profile '{camera_name}'. Known profiles: {known}")

    red_idx = camera["red"]
    nir_idx = camera["nir"]

    print(f"[AgriVision] Computing NDVI using camera profile: {camera_name}")
    print(f"  RED band index: {red_idx}")
    print(f"  NIR band index: {nir_idx}")
    print(f"  Orthophoto path: {ORTHO_PATH}")

    if not ORTHO_PATH.exists():
        raise FileNotFoundError(f"Orthophoto not found: {ORTHO_PATH}")

    with rasterio.open(ORTHO_PATH) as src:
        if src.count < max(red_idx, nir_idx):
            raise RuntimeError(
                f"Orthophoto has only {src.count} bands; cannot access RED={red_idx}, NIR={nir_idx}"
            )

        red = src.read(red_idx)
        nir = src.read(nir_idx)

        ndvi = compute_ndvi_array(red, nir)
        save_ndvi_geotiff(src, ndvi, NDVI_TIF_OUT)
        save_ndvi_png(ndvi, NDVI_PNG_OUT)

    print("[AgriVision] NDVI computation completed.")


if __name__ == "__main__":
    run_ndvi()

