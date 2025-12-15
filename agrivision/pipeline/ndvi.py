#!/usr/bin/env python3
"""
agrivision.pipeline.ndvi

Compute a vegetation index from an orthophoto and save:

  - GeoTIFF:  output/ndvi/ndvi.tif
  - Color PNG: output/ndvi/ndvi_color.png

IMPORTANT (2025):
-----------------

This module now supports multiple index modes:

MAPIR (preferred, if MAPIR orthophoto exists)
  - index_mode = "nir_green"  -> (NIR - GREEN) / (NIR + GREEN)   (GNDVI-like)
  - index_mode = "nir_red"    -> (NIR - RED) / (NIR + RED)       (true NDVI)

RGB fallback (if MAPIR orthophoto is missing)
  - index_mode = "pseudo"     -> uses configured bands (may not be true NDVI)

Why:
  Your MAPIR ODM orthophoto may be RGBA where "Red" channel actually contains NIR
  (false-color). In that case there is no clean RED band for true NDVI, so we compute
  a NIR/GREEN vegetation index instead.

Output filenames remain ndvi.tif / ndvi_color.png for backwards compatibility.
In a later step, we can rename outputs and update the report wording.
"""

from pathlib import Path
from typing import Dict, Tuple

import matplotlib.pyplot as plt
import numpy as np
import rasterio

from agrivision.utils.settings import get_project_root, load_config


CONFIG = load_config()
PROJECT_ROOT = get_project_root()

# Paths to orthophotos
ORTHO_RGB = (
    PROJECT_ROOT / CONFIG["paths"]["odm_project_root_rgb"]
    / "project/odm_orthophoto/odm_orthophoto.tif"
)

ORTHO_MAPIR = (
    PROJECT_ROOT / CONFIG["paths"]["odm_project_root_mapir"]
    / "project/odm_orthophoto/odm_orthophoto.tif"
)

# NDVI output folder
OUT_DIR = PROJECT_ROOT / CONFIG["paths"]["ndvi_output"]
OUT_TIF = OUT_DIR / "ndvi.tif"
OUT_PNG = OUT_DIR / "ndvi_color.png"

# Thresholds (used elsewhere, printed here for clarity)
POOR_MAX = CONFIG["ndvi"]["poor_max"]
MEDIUM_MAX = CONFIG["ndvi"]["medium_max"]

MAPIR_PROFILE: Dict = CONFIG["ndvi"]["mapir_profile"]
RGB_PROFILE: Dict = CONFIG["ndvi"]["rgb_profile"]


# ---------------------------------------------------------------------
# Source selection
# ---------------------------------------------------------------------
def _exists(p: Path) -> bool:
    return p.exists()


def choose_source() -> Tuple[Path, str, Dict]:
    """
    Choose which orthophoto to compute from.

    Returns:
      (path, label, profile_dict)
    """
    if _exists(ORTHO_MAPIR):
        return ORTHO_MAPIR, "MAPIR", MAPIR_PROFILE

    if _exists(ORTHO_RGB):
        return ORTHO_RGB, "RGB", RGB_PROFILE

    raise RuntimeError(
        "\n[ERROR] No orthophoto found for vegetation index computation.\n"
        f"Expected at least one of:\n"
        f"  - MAPIR: {ORTHO_MAPIR}\n"
        f"  - RGB  : {ORTHO_RGB}\n"
        "Run ODM before running this step.\n"
    )


# ---------------------------------------------------------------------
# Index computation
# ---------------------------------------------------------------------
def _read_band(src: rasterio.io.DatasetReader, band_idx: int) -> np.ndarray:
    if band_idx is None:
        raise ValueError("Band index is None.")
    if band_idx < 1 or band_idx > src.count:
        raise ValueError(
            f"Invalid band index {band_idx}. Available bands: 1..{src.count}"
        )
    return src.read(band_idx).astype("float32")


def compute_index(src: rasterio.io.DatasetReader, label: str, profile: Dict) -> Tuple[np.ndarray, str]:
    """
    Compute vegetation index based on profile['index_mode'].

    Returns:
      (index_array, human_readable_index_name)
    """
    mode = (profile.get("index_mode") or "").strip().lower()

    if mode == "nir_red":
        # True NDVI
        nir_idx = profile.get("nir_band")
        red_idx = profile.get("red_band")
        nir = _read_band(src, int(nir_idx))
        red = _read_band(src, int(red_idx))
        name = "NDVI (NIR-RED)"
        print(f"[NDVI] {label} index_mode=nir_red → computing {name}")
        return _normalized_diff(nir, red), name

    if mode == "nir_green":
        # GNDVI-like
        nir_idx = profile.get("nir_band")
        green_idx = profile.get("green_band")
        nir = _read_band(src, int(nir_idx))
        green = _read_band(src, int(green_idx))
        name = "Vegetation Index (NIR-GREEN, GNDVI-like)"
        print(f"[NDVI] {label} index_mode=nir_green → computing {name}")
        return _normalized_diff(nir, green), name

    if mode == "pseudo":
        # Backwards-compatible pseudo index using configured "nir_band" and "red_band"
        nir_idx = profile.get("nir_band")
        red_idx = profile.get("red_band")
        nir = _read_band(src, int(nir_idx))
        red = _read_band(src, int(red_idx))
        name = "Pseudo Vegetation Index (configured bands)"
        print(f"[NDVI] {label} index_mode=pseudo → computing {name}")
        return _normalized_diff(nir, red), name

    raise ValueError(
        f"[NDVI] Unsupported index_mode '{mode}' for {label} profile. "
        "Supported: 'nir_red', 'nir_green', 'pseudo'."
    )


def _normalized_diff(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """
    (a - b) / (a + b), with epsilon to avoid divide-by-zero.
    """
    denom = a + b
    eps = 1e-6
    idx = (a - b) / (denom + eps)
    return np.clip(idx, -1.0, 1.0)


# ---------------------------------------------------------------------
# Output writers
# ---------------------------------------------------------------------
def save_geotiff(src: rasterio.io.DatasetReader, arr: np.ndarray, out_path: Path) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    profile = src.profile.copy()
    profile.update(
        dtype=rasterio.float32,
        count=1,
        nodata=None,
    )

    with rasterio.open(out_path, "w", **profile) as dst:
        dst.write(arr.astype(rasterio.float32), 1)

    print(f"[NDVI] GeoTIFF saved: {out_path}")


def save_png(arr: np.ndarray, out_path: Path, title: str) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    valid = np.isfinite(arr)
    if not np.any(valid):
        raise RuntimeError("[NDVI] No valid values to render.")

    vals = arr[valid]
    vmin, vmax = np.percentile(vals, [2, 98])
    if vmin == vmax:
        vmin -= 0.1
        vmax += 0.1

    print(f"[NDVI] Rendering PNG with vmin={vmin:.3f}, vmax={vmax:.3f}")

    plt.figure(figsize=(10, 8))
    im = plt.imshow(arr, cmap="RdYlGn", vmin=vmin, vmax=vmax)
    plt.colorbar(im, label="Index value")
    plt.title(title)
    plt.tight_layout()
    plt.savefig(out_path, dpi=200)
    plt.close()

    print(f"[NDVI] PNG saved: {out_path}")


# ---------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------
def run_ndvi() -> None:
    """
    Compute vegetation index from MAPIR or RGB orthophoto (auto-selected).
    """
    print("\n[AgriVision] Vegetation index computation starting...")
    print(f"  thresholds: poor_max={POOR_MAX}, medium_max={MEDIUM_MAX}")

    src_path, label, profile = choose_source()
    print(f"[NDVI] Source orthophoto: {src_path} ({label})")

    with rasterio.open(src_path) as src:
        idx, idx_name = compute_index(src, label, profile)
        save_geotiff(src, idx, OUT_TIF)
        save_png(idx, OUT_PNG, title=idx_name)

    print("[AgriVision] Vegetation index computation completed.")


if __name__ == "__main__":
    run_ndvi()
