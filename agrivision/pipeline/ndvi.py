#!/usr/bin/env python3
"""
agrivision.pipeline.ndvi

Compute a vegetation index from an orthophoto and save:

  - GeoTIFF:  output/ndvi/ndvi.tif
  - Color PNG: output/ndvi/ndvi_color.png

NEW (Priority 1 - Metadata):
----------------------------
After computation, write a self-describing metadata file:

  output/ndvi/metadata.json

This helps SIP7-style auditability and makes results reproducible.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Tuple

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

# Output folder
OUT_DIR = PROJECT_ROOT / CONFIG["paths"]["ndvi_output"]
OUT_TIF = OUT_DIR / "ndvi.tif"
OUT_PNG = OUT_DIR / "ndvi_color.png"
OUT_META = OUT_DIR / "metadata.json"

# Thresholds (used by grid/report)
POOR_MAX = float(CONFIG["ndvi"]["poor_max"])
MEDIUM_MAX = float(CONFIG["ndvi"]["medium_max"])

MAPIR_PROFILE: Dict[str, Any] = CONFIG["ndvi"]["mapir_profile"]
RGB_PROFILE: Dict[str, Any] = CONFIG["ndvi"]["rgb_profile"]


# ---------------------------------------------------------------------
# Source selection
# ---------------------------------------------------------------------
def _exists(p: Path) -> bool:
    return p.exists()


def choose_source() -> Tuple[Path, str, Dict[str, Any]]:
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
    if band_idx < 1 or band_idx > src.count:
        raise ValueError(
            f"Invalid band index {band_idx}. Available bands: 1..{src.count}"
        )
    return src.read(band_idx).astype("float32")


def _normalized_diff(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """
    (a - b) / (a + b), with epsilon to avoid divide-by-zero.
    """
    denom = a + b
    eps = 1e-6
    idx = (a - b) / (denom + eps)
    return np.clip(idx, -1.0, 1.0)


def compute_index(
    src: rasterio.io.DatasetReader,
    label: str,
    profile: Dict[str, Any],
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """
    Compute vegetation index based on profile['index_mode'].

    Returns:
      (index_array, meta_index_block)

    meta_index_block includes:
      - index_name
      - formula
      - band_mapping
      - index_mode
    """
    mode = (profile.get("index_mode") or "").strip().lower()

    if mode == "nir_red":
        nir_idx = int(profile["nir_band"])
        red_idx = int(profile["red_band"])
        nir = _read_band(src, nir_idx)
        red = _read_band(src, red_idx)

        meta = {
            "index_mode": "nir_red",
            "index_name": "NDVI",
            "formula": "(NIR - RED) / (NIR + RED)",
            "band_mapping": {"nir_band": nir_idx, "red_band": red_idx},
        }
        print(f"[VI] {label} index_mode=nir_red → computing NDVI (true NDVI)")
        return _normalized_diff(nir, red), meta

    if mode == "nir_green":
        nir_idx = int(profile["nir_band"])
        green_idx = int(profile["green_band"])
        nir = _read_band(src, nir_idx)
        green = _read_band(src, green_idx)

        meta = {
            "index_mode": "nir_green",
            "index_name": "GNDVI-like Vegetation Index",
            "formula": "(NIR - GREEN) / (NIR + GREEN)",
            "band_mapping": {"nir_band": nir_idx, "green_band": green_idx},
        }
        print(f"[VI] {label} index_mode=nir_green → computing Vegetation Index (GNDVI-like)")
        return _normalized_diff(nir, green), meta

    if mode == "pseudo":
        nir_idx = int(profile["nir_band"])
        red_idx = int(profile["red_band"])
        nir = _read_band(src, nir_idx)
        red = _read_band(src, red_idx)

        meta = {
            "index_mode": "pseudo",
            "index_name": "Pseudo Vegetation Index",
            "formula": "(B2 - B1) / (B2 + B1)  (configured bands)",
            "band_mapping": {"band_a": nir_idx, "band_b": red_idx},
        }
        print(f"[VI] {label} index_mode=pseudo → computing pseudo vegetation index")
        return _normalized_diff(nir, red), meta

    raise ValueError(
        f"[VI] Unsupported index_mode '{mode}' for {label} profile. "
        "Supported: 'nir_red', 'nir_green', 'pseudo'."
    )


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

    print(f"[VI] GeoTIFF saved: {out_path}")


def save_png(arr: np.ndarray, out_path: Path, title: str) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    valid = np.isfinite(arr)
    if not np.any(valid):
        raise RuntimeError("[VI] No valid values to render.")

    vals = arr[valid]
    vmin, vmax = np.percentile(vals, [2, 98])
    if vmin == vmax:
        vmin -= 0.1
        vmax += 0.1

    print(f"[VI] Rendering PNG with vmin={vmin:.3f}, vmax={vmax:.3f}")

    plt.figure(figsize=(10, 8))
    im = plt.imshow(arr, cmap="RdYlGn", vmin=vmin, vmax=vmax)
    plt.colorbar(im, label="Index value")
    plt.title(title)
    plt.tight_layout()
    plt.savefig(out_path, dpi=200)
    plt.close()

    print(f"[VI] PNG saved: {out_path}")


def save_metadata(meta: Dict[str, Any], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
    print(f"[VI] Metadata saved: {out_path}")


# ---------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------
def run_ndvi() -> None:
    """
    Compute vegetation index from MAPIR or RGB orthophoto (auto-selected),
    write outputs, and emit metadata.json for traceability.
    """
    print("\n[AgriVision] Vegetation index computation starting...")
    print(f"  thresholds: poor_max={POOR_MAX}, medium_max={MEDIUM_MAX}")

    src_path, label, profile = choose_source()
    print(f"[VI] Source orthophoto: {src_path} ({label})")

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    with rasterio.open(src_path) as src:
        idx, idx_meta = compute_index(src, label, profile)
        save_geotiff(src, idx, OUT_TIF)
        save_png(idx, OUT_PNG, title=idx_meta["index_name"])

        meta = {
            "generated_at_utc": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
            "source": {
                "dataset": label,
                "orthophoto_path": str(src_path),
                "band_count": int(src.count),
            },
            "index": idx_meta,
            "classification_thresholds": {
                "poor_max": POOR_MAX,
                "medium_max": MEDIUM_MAX,
            },
            "artifacts": {
                "geotiff": str(OUT_TIF),
                "png": str(OUT_PNG),
                "metadata": str(OUT_META),
            },
            "notes": [
                "If index_mode is 'nir_green', this is a GNDVI-like vegetation index (not true NDVI).",
                "Thresholds are user-configurable and may be calibrated per crop/season/sensor.",
            ],
        }

    save_metadata(meta, OUT_META)
    print("[AgriVision] Vegetation index computation completed.")


if __name__ == "__main__":
    run_ndvi()
