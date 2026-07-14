#!/usr/bin/env python3
"""
agrivision.pipeline.stages.vegetation_index

Compute a vegetation index from an orthophoto and save:

  - GeoTIFF:  output/vegetation_index/vegetation_index.tif
  - Color PNG: output/vegetation_index/vegetation_index_color.png

NEW (Priority 1 - Metadata):
----------------------------
After computation, write a self-describing metadata file:

  output/vegetation_index/metadata.json

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
from rasterio.enums import Resampling
from rasterio.windows import Window

from agrivision.pipeline.io.paths import resolve_pipeline_paths


def _get_vegetation_index_settings(
    workspace_root: Path | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    resolved = resolve_pipeline_paths(workspace_root=workspace_root, config=config)
    config = resolved["config"]
    vegetation_index_config = config["vegetation_index"]
    out_dir = resolved["vegetation_index_output"]

    return {
        "project_root": resolved["project_root"],
        "ortho_rgb": resolved["ortho_rgb"],
        "ortho_mapir": resolved["ortho_mapir"],
        "out_dir": out_dir,
        "out_tif": out_dir / "vegetation_index.tif",
        "out_png": out_dir / "vegetation_index_color.png",
        "out_meta": out_dir / "metadata.json",
        "poor_max": float(vegetation_index_config["poor_max"]),
        "medium_max": float(vegetation_index_config["medium_max"]),
        "mapir_profile": vegetation_index_config["mapir_profile"],
        "rgb_profile": vegetation_index_config["rgb_profile"],
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


def _valid_source_mask(
    src: rasterio.io.DatasetReader,
    *bands: np.ndarray,
) -> np.ndarray:
    mask = np.ones(bands[0].shape, dtype=bool)
    for band in bands:
        mask &= np.isfinite(band)

    if src.nodata is not None:
        for band in bands:
            mask &= band != src.nodata

    if src.count >= 4:
        alpha = src.read(4)
        mask &= alpha > 0

    return mask


def _normalized_diff(
    a: np.ndarray,
    b: np.ndarray,
    valid_mask: np.ndarray | None = None,
) -> np.ndarray:
    """
    (a - b) / (a + b), with epsilon to avoid divide-by-zero.
    """
    eps = 1e-6
    denom = a + b
    valid = np.isfinite(a) & np.isfinite(b) & (denom > eps)
    if valid_mask is not None:
        valid &= valid_mask

    idx = np.full(a.shape, np.nan, dtype="float32")
    idx[valid] = (a[valid] - b[valid]) / denom[valid]
    return np.clip(idx, -1.0, 1.0)


def _index_definition(label: str, profile: Dict[str, Any]) -> tuple[str, int, int, Dict[str, Any]]:
    mode = (profile.get("index_mode") or "").strip().lower()
    if mode == "nir_red":
        nir_idx = int(profile["nir_band"])
        red_idx = int(profile["red_band"])
        return mode, nir_idx, red_idx, {
            "index_mode": "nir_red",
            "index_name": "Vegetation Index",
            "formula": "(NIR - RED) / (NIR + RED)",
            "band_mapping": {"nir_band": nir_idx, "red_band": red_idx},
        }
    if mode == "nir_green":
        nir_idx = int(profile["nir_band"])
        green_idx = int(profile["green_band"])
        return mode, nir_idx, green_idx, {
            "index_mode": "nir_green",
            "index_name": "Vegetation Index",
            "formula": "(NIR - GREEN) / (NIR + GREEN)",
            "band_mapping": {"nir_band": nir_idx, "green_band": green_idx},
        }
    if mode == "pseudo":
        nir_idx = int(profile["nir_band"])
        red_idx = int(profile["red_band"])
        return mode, nir_idx, red_idx, {
            "index_mode": "pseudo",
            "index_name": "Pseudo Vegetation Index",
            "formula": "(B2 - B1) / (B2 + B1)  (configured bands)",
            "band_mapping": {"band_a": nir_idx, "band_b": red_idx},
        }
    raise ValueError(
        f"[VI] Unsupported index_mode '{mode}' for {label} profile. "
        "Supported: 'nir_red', 'nir_green', 'pseudo'."
    )


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
        valid_mask = _valid_source_mask(src, nir, red)

        meta = {
            "index_mode": "nir_red",
            "index_name": "Vegetation Index",
            "formula": "(NIR - RED) / (NIR + RED)",
            "band_mapping": {"nir_band": nir_idx, "red_band": red_idx},
        }
        print(f"[VI] {label} index_mode=nir_red â†’ computing Vegetation Index (a true vegetation index)")
        return _normalized_diff(nir, red, valid_mask), meta

    if mode == "nir_green":
        nir_idx = int(profile["nir_band"])
        green_idx = int(profile["green_band"])
        nir = _read_band(src, nir_idx)
        green = _read_band(src, green_idx)
        valid_mask = _valid_source_mask(src, nir, green)

        meta = {
            "index_mode": "nir_green",
            "index_name": "Vegetation Index",
            "formula": "(NIR - GREEN) / (NIR + GREEN)",
            "band_mapping": {"nir_band": nir_idx, "green_band": green_idx},
        }
        print(f"[VI] {label} index_mode=nir_green â†’ computing Vegetation Index")
        return _normalized_diff(nir, green, valid_mask), meta

    if mode == "pseudo":
        nir_idx = int(profile["nir_band"])
        red_idx = int(profile["red_band"])
        nir = _read_band(src, nir_idx)
        red = _read_band(src, red_idx)
        valid_mask = _valid_source_mask(src, nir, red)

        meta = {
            "index_mode": "pseudo",
            "index_name": "Pseudo Vegetation Index",
            "formula": "(B2 - B1) / (B2 + B1)  (configured bands)",
            "band_mapping": {"band_a": nir_idx, "band_b": red_idx},
        }
        print(f"[VI] {label} index_mode=pseudo â†’ computing pseudo vegetation index")
        return _normalized_diff(nir, red, valid_mask), meta

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
        nodata=np.nan,
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
    plt.imshow(arr, cmap="RdYlGn", vmin=vmin, vmax=vmax)
    plt.axis("off")
    plt.tight_layout(pad=0)
    plt.savefig(out_path, dpi=200, bbox_inches="tight", pad_inches=0)
    plt.close()

    print(f"[VI] PNG saved: {out_path}")


def save_metadata(meta: Dict[str, Any], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
    print(f"[VI] Metadata saved: {out_path}")


def summarize_index_quality(idx: np.ndarray) -> dict[str, Any]:
    valid = np.isfinite(idx)
    total = int(valid.size)
    count = int(valid.sum())
    if count == 0:
        return {
            "valid_pixels": {"count": 0, "total": total, "percent": 0.0},
            "distribution": {},
            "quality_flags": ["No valid vegetation-index pixels were produced."],
        }

    values = idx[valid]
    percentiles = {
        str(q): float(np.nanpercentile(values, q))
        for q in (2, 10, 33, 50, 66, 90, 98)
    }
    saturated_high_percent = float(np.mean(values >= 0.95) * 100.0)
    saturated_low_percent = float(np.mean(values <= -0.95) * 100.0)

    flags: list[str] = []
    if saturated_high_percent >= 50.0:
        flags.append(
            "Index distribution is highly saturated near 1.0; verify sensor band mapping and source calibration before agronomic interpretation."
        )
    if saturated_low_percent >= 50.0:
        flags.append(
            "Index distribution is highly saturated near -1.0; verify sensor band mapping and source calibration before agronomic interpretation."
        )

    return {
        "valid_pixels": {
            "count": count,
            "total": total,
            "percent": float(count / total * 100.0),
        },
        "distribution": {
            "min": float(np.nanmin(values)),
            "max": float(np.nanmax(values)),
            "mean": float(np.nanmean(values)),
            "median": float(np.nanmedian(values)),
            "std": float(np.nanstd(values)),
            "percentiles": percentiles,
            "saturated_high_percent": saturated_high_percent,
            "saturated_low_percent": saturated_low_percent,
        },
        "quality_flags": flags,
    }


def _summarize_index_sample(total: int, count: int, sample: np.ndarray) -> dict[str, Any]:
    if count == 0 or sample.size == 0:
        return {
            "valid_pixels": {"count": count, "total": total, "percent": 0.0},
            "distribution": {},
            "quality_flags": ["No valid vegetation-index pixels were produced."],
        }

    values = sample[np.isfinite(sample)]
    percentiles = {
        str(q): float(np.nanpercentile(values, q))
        for q in (2, 10, 33, 50, 66, 90, 98)
    }
    saturated_high_percent = float(np.mean(values >= 0.95) * 100.0)
    saturated_low_percent = float(np.mean(values <= -0.95) * 100.0)
    flags: list[str] = []
    if saturated_high_percent >= 50.0:
        flags.append(
            "Index distribution is highly saturated near 1.0; verify sensor band mapping and source calibration before agronomic interpretation."
        )
    if saturated_low_percent >= 50.0:
        flags.append(
            "Index distribution is highly saturated near -1.0; verify sensor band mapping and source calibration before agronomic interpretation."
        )
    flags.append("Distribution statistics were estimated from a block sample to keep memory use bounded.")
    return {
        "valid_pixels": {
            "count": count,
            "total": total,
            "percent": float(count / total * 100.0),
        },
        "distribution": {
            "min": float(np.nanmin(values)),
            "max": float(np.nanmax(values)),
            "mean": float(np.nanmean(values)),
            "median": float(np.nanmedian(values)),
            "std": float(np.nanstd(values)),
            "percentiles": percentiles,
            "saturated_high_percent": saturated_high_percent,
            "saturated_low_percent": saturated_low_percent,
        },
        "quality_flags": flags,
    }


def _save_png_from_tif(tif_path: Path, out_path: Path, title: str, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    with rasterio.open(tif_path) as src:
        max_edge = 1800
        scale = min(1.0, max_edge / max(src.width, src.height))
        height = max(1, int(src.height * scale))
        width = max(1, int(src.width * scale))
        arr = src.read(
            1,
            out_shape=(height, width),
            masked=True,
            resampling=Resampling.average,
        ).filled(np.nan).astype("float32")
    save_png(arr, out_path, title=title, out_dir=out_dir)


def compute_index_streaming(
    src: rasterio.io.DatasetReader,
    label: str,
    profile: Dict[str, Any],
    out_tif: Path,
    out_png: Path,
    out_dir: Path,
) -> tuple[Dict[str, Any], dict[str, Any]]:
    mode, first_idx, second_idx, idx_meta = _index_definition(label, profile)
    if first_idx < 1 or first_idx > src.count or second_idx < 1 or second_idx > src.count:
        raise ValueError(f"Invalid band mapping for {label}. Available bands: 1..{src.count}")

    print(f"[VI] {label} index_mode={mode} -> computing in memory-safe blocks")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_profile = src.profile.copy()
    out_profile.update(dtype=rasterio.float32, count=1, nodata=np.nan, tiled=True, blockxsize=512, blockysize=512)

    total_pixels = int(src.width * src.height)
    valid_pixels = 0
    samples: list[np.ndarray] = []
    chunk_size = 1024
    with rasterio.open(out_tif, "w", **out_profile) as dst:
        for row in range(0, src.height, chunk_size):
            height = min(chunk_size, src.height - row)
            for col in range(0, src.width, chunk_size):
                width = min(chunk_size, src.width - col)
                window = Window(col, row, width, height)
                first = src.read(first_idx, window=window).astype("float32")
                second = src.read(second_idx, window=window).astype("float32")
                valid_mask = np.isfinite(first) & np.isfinite(second)
                if src.nodata is not None:
                    valid_mask &= first != src.nodata
                    valid_mask &= second != src.nodata
                if src.count >= 4:
                    valid_mask &= src.read(4, window=window) > 0
                idx = _normalized_diff(first, second, valid_mask)
                dst.write(idx, 1, window=window)

                valid = idx[np.isfinite(idx)]
                valid_pixels += int(valid.size)
                if valid.size:
                    step = max(1, valid.size // 5000)
                    samples.append(valid[::step].astype("float32", copy=False))

    sample = np.concatenate(samples) if samples else np.array([], dtype="float32")
    quality = _summarize_index_sample(total_pixels, valid_pixels, sample)
    print(f"[VI] GeoTIFF saved: {out_tif}")
    _save_png_from_tif(out_tif, out_png, title=idx_meta["index_name"], out_dir=out_dir)
    return idx_meta, quality


# ---------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------
def run_vegetation_index(
    workspace_root: Path | None = None,
    config: dict[str, Any] | None = None,
) -> None:
    """
    Compute vegetation index from MAPIR or RGB orthophoto (auto-selected),
    write outputs, and emit metadata.json for traceability.
    """
    settings = _get_vegetation_index_settings(workspace_root=workspace_root, config=config)
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
        pixel_count = int(src.width * src.height)
        if pixel_count > 30_000_000:
            idx_meta, quality = compute_index_streaming(
                src,
                label,
                profile,
                out_tif,
                out_png,
                out_dir,
            )
        else:
            idx, idx_meta = compute_index(src, label, profile)
            quality = summarize_index_quality(idx)
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
            "valid_pixels": quality["valid_pixels"],
            "distribution": quality["distribution"],
            "quality_flags": quality["quality_flags"],
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
    run_vegetation_index()
