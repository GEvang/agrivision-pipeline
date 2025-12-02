#!/usr/bin/env python3
"""
compute_ndvi.py

Read the orthophoto produced by ODM and compute NDVI, then:

  - Save NDVI GeoTIFF to output/ndvi/ndvi.tif
  - Save a color PNG to output/ndvi/ndvi_color.png

Usage (from project root):

    source venv/bin/activate
    python3 scripts/compute_ndvi.py --camera sample_mapir_unknown
"""

import argparse
from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.shutil import copy as rio_copy
import matplotlib.pyplot as plt

BASE_DIR = Path(__file__).resolve().parent.parent

ORTHO_PATH = BASE_DIR / "data" / "odm_project" / "project" / "odm_orthophoto" / "odm_orthophoto.tif"
NDVI_TIF_OUT = BASE_DIR / "output" / "ndvi" / "ndvi.tif"
NDVI_PNG_OUT = BASE_DIR / "output" / "ndvi" / "ndvi_color.png"

# Simple camera profiles: which band is RED, which is NIR.
# You can extend this later when you know the actual camera setups.
CAMERA_PROFILES = {
    "sample_mapir_unknown": {
        "red": 1,  # band index (1-based) for RED
        "nir": 2,  # band index (1-based) for NIR
    },
    # Add other cameras here as needed
}


def compute_ndvi_array(red: np.ndarray, nir: np.ndarray) -> np.ndarray:
    """
    Compute NDVI = (NIR - RED) / (NIR + RED) with safe handling of division.
    """
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
    """
    Save NDVI array to GeoTIFF using georeferencing from template_src.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)

    profile = template_src.profile.copy()
    profile.update(
        dtype="float32",
        count=1,
        nodata=np.nan,
    )

    with rasterio.open(out_path, "w", **profile) as dst:
        dst.write(ndvi, 1)

    print(f"[OK] NDVI GeoTIFF saved to {out_path}")


def save_ndvi_png(ndvi: np.ndarray, out_path: Path) -> None:
    """
    Save a colorized NDVI PNG for quick visualization.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Limit NDVI to [-1, 1] and normalize to [0, 1]
    ndvi_clipped = np.clip(ndvi, -1.0, 1.0)
    ndvi_norm = (ndvi_clipped + 1.0) / 2.0

    # Mask no-data as bright red
    mask = ~np.isfinite(ndvi_clipped)

    cmap = plt.get_cmap("YlGn")
    rgba = cmap(ndvi_norm)  # shape (H, W, 4)
    rgba[mask] = [0.6, 0.0, 0.0, 1.0]  # dark red background

    plt.figure(figsize=(6, 6))
    plt.imshow(rgba, origin="upper")
    plt.axis("off")
    plt.tight_layout(pad=0)
    plt.savefig(out_path, dpi=300, bbox_inches="tight", pad_inches=0)
    plt.close()

    print(f"[OK] NDVI color PNG saved to {out_path}")


def main():
    parser = argparse.ArgumentParser(description="Compute NDVI from ODM orthophoto.")
    parser.add_argument(
        "--camera",
        type=str,
        default="sample_mapir_unknown",
        help="Camera profile name for band mapping (red/nir).",
    )
    args = parser.parse_args()

    camera = CAMERA_PROFILES.get(args.camera)
    if camera is None:
        raise ValueError(
            f"Unknown camera profile '{args.camera}'. "
            f"Known profiles: {', '.join(CAMERA_PROFILES.keys())}"
        )

    red_band_idx = camera["red"]
    nir_band_idx = camera["nir"]

    print(f"[AgriVision] Using camera profile: {args.camera}")
    print(f"  RED band index: {red_band_idx}")
    print(f"  NIR band index: {nir_band_idx}")

    if not ORTHO_PATH.exists():
        raise FileNotFoundError(f"Orthophoto not found: {ORTHO_PATH}")

    with rasterio.open(ORTHO_PATH) as src:
        if src.count < max(red_band_idx, nir_band_idx):
            raise RuntimeError(
                f"Orthophoto has only {src.count} band(s), cannot access "
                f"RED={red_band_idx}, NIR={nir_band_idx}"
            )

        red = src.read(red_band_idx)
        nir = src.read(nir_band_idx)

        ndvi = compute_ndvi_array(red, nir)
        save_ndvi_geotiff(src, ndvi, NDVI_TIF_OUT)
        save_ndvi_png(ndvi, NDVI_PNG_OUT)


if __name__ == "__main__":
    main()

