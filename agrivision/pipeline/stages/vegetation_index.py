#!/usr/bin/env python3
"""
agrivision.pipeline.stages.vegetation_index

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

from agrivision.config.settings import get_project_root, load_config


def _get_ndvi_settings() -> dict[str, Any]:
    config = load_config()
    project_root = get_project_root()
    paths = config["paths"]
    ndvi_config = config["ndvi"]

    out_dir = project_root / paths["ndvi_output"]

    return {
        "project_root": project_root,
        "ortho_rgb": project_root / paths["odm_project_root_rgb"] / "project/odm_orthophoto/odm_orthophoto.tif",
        "ortho_mapir": project_root / paths["odm_project_root_mapir"] / "project/odm_orthophoto/odm_orthophoto.tif",
        "out_dir": out_dir,
        "out_tif": out_dir / "ndvi.tif",
        "out_png": out_dir / "ndvi_color.png",
        "out_meta": out_dir / "metadata.json",
        "poor_max": float(ndvi_config["poor_max"]),
        "medium_max": float(ndvi_config["medium_max"]),
        "mapir_profile": ndvi_config["mapir_profile"],
        "rgb_profile": ndvi_config["rgb_profile"],
    }


# ---------------------------------------------------------------------
# Source selection
# ---------------------------------------------------------------------
def _exists(p: Path) -> bool:
    return p.exists()


def choose_source(
    ortho_mapir: Path,
    ortho_rgb: Path,
    mapir_profile: Dict[str, Any],
    rgb_profile: Dict[str, Any],
) -> Tuple[Path, str, Dict[str, Any]]:
    """
    Choose which orthophoto to compute from.

    Returns:
      (path, label, profile_dict)
    """
    if _exists(ortho_mapir):
        return ortho_mapir, "MAPIR", mapir_profile

    if _exists(ortho_rgb):
        return ortho_rgb, "RGB", rgb_profile

    raise RuntimeError(
        "\n[ERROR] No orthophoto found for vegetation index computation.\n"
        f"Expected at least one of:\n"
        f"  - MAPIR: {ortho_mapir}\n"
        f"  - RGB  : {ortho_rgb}\n"
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
            "index_name": "Vegetation Index",
            "formula": "(NIR - GREEN) / (NIR + GREEN)",
            "band_mapping": {"nir_band": nir_idx, "green_band": green_idx},
        }
        print(f"[VI] {label} index_mode=nir_green → computing Vegetation Index")
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
def save_geotiff(
    src: rasterio.io.DatasetReader,
    arr: np.ndarray,
    out_path: Path,
    out_dir: Path,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    profile = src.profile.copy()
    profile.update(
        dtype=rasterio.float32,
        count=1,
        nodata=None,
    )

    with rasterio.open(out_path, "w", **profile) as dst:
        dst.write(arr.astype(rasterio.float32), 1)

    print(f"[VI] GeoTIFF saved: {out_path}")


def save_png(arr: np.ndarray, out_path: Path, title: str, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

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
    settings = _get_ndvi_settings()
    ortho_rgb = settings["ortho_rgb"]
    ortho_mapir = settings["ortho_mapir"]
    out_dir = settings["out_dir"]
    out_tif = settings["out_tif"]
    out_png = settings["out_png"]
    out_meta = settings["out_meta"]
    poor_max = settings["poor_max"]
    medium_max = settings["medium_max"]
    mapir_profile = settings["mapir_profile"]
    rgb_profile = settings["rgb_profile"]

    print("\n[AgriVision] Vegetation index computation starting...")
    print(f"  thresholds: poor_max={poor_max}, medium_max={medium_max}")

    src_path, label, profile = choose_source(
        ortho_mapir,
        ortho_rgb,
        mapir_profile,
        rgb_profile,
    )
    print(f"[VI] Source orthophoto: {src_path} ({label})")

    out_dir.mkdir(parents=True, exist_ok=True)

    with rasterio.open(src_path) as src:
        idx, idx_meta = compute_index(src, label, profile)
        save_geotiff(src, idx, out_tif, out_dir)
        save_png(idx, out_png, title=idx_meta["index_name"], out_dir=out_dir)

        meta = {
            "generated_at_utc": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
            "source": {
                "dataset": label,
                "orthophoto_path": str(src_path),
                "band_count": int(src.count),
            },
            "index": idx_meta,
            "classification_thresholds": {
                "poor_max": poor_max,
                "medium_max": medium_max,
            },
            "artifacts": {
                "geotiff": str(out_tif),
                "png": str(out_png),
                "metadata": str(out_meta),
            },
            "notes": [
                "If index_mode is 'nir_green', this vegetation index is computed from NIR and green bands.",
                "Thresholds are user-configurable and may be calibrated per crop/season/sensor.",
            ],
        }

    save_metadata(meta, out_meta)
    print("[AgriVision] Vegetation index computation completed.")


if __name__ == "__main__":
    run_ndvi()
