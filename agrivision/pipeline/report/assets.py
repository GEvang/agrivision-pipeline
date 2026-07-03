"""Asset discovery and data loading helpers for the HTML report stage."""

from __future__ import annotations

import csv
import json
from json import JSONDecodeError
from pathlib import Path
from typing import Any, Dict, List

from agrivision.pipeline.io.paths import resolve_pipeline_paths
import numpy as np
import rasterio
from PIL import Image, UnidentifiedImageError


def get_report_settings(
    workspace_root: Path | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    resolved = resolve_pipeline_paths(workspace_root=workspace_root, config=config)
    output_dir = resolved["output_root"]
    report_path = resolved["report_path"]
    ndvi_dir = resolved["ndvi_output"]
    weather_dir = output_dir / "weather"
    report_assets_dir = output_dir / "report_assets"
    return {
        "config": resolved["config"],
        "output_dir": output_dir,
        "report_path": report_path,
        "report_assets_dir": report_assets_dir,
        "ndvi_dir": ndvi_dir,
        "weather_dir": weather_dir,
        "orthophoto_rgb": resolved["ortho_rgb"],
        "orthophoto_mapir": resolved["ortho_mapir"],
        "orthophoto_thermal": resolved["ortho_thermal"],
        "orthophoto_rgb_preview": report_assets_dir / "visible_orthomosaic.png",
        "orthophoto_mapir_preview": report_assets_dir / "mapir_placeholder.png",
        "orthophoto_thermal_preview": report_assets_dir / "thermal_orthomosaic.png",
        "ndvi_meta_path": ndvi_dir / "metadata.json",
        "grid_meta_path": ndvi_dir / "grid_metadata.json",
        "ndvi_tif": ndvi_dir / "ndvi.tif",
        "ndvi_color_png": ndvi_dir / "ndvi_color.png",
        "grid_overlay_png": ndvi_dir / "ndvi_grid_overlay.png",
        "grid_cells_csv": ndvi_dir / "ndvi_grid_cells.csv",
        "grid_categories_csv": ndvi_dir / "ndvi_grid_categories.csv",
        "disease_risk_summary": ndvi_dir / "disease_risk" / "summary.json",
    }



def rel_to_report(abs_path: Path, output_dir: Path) -> str:
    try:
        rel = abs_path.relative_to(output_dir)
        return rel.as_posix()
    except ValueError:
        return abs_path.name



def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, JSONDecodeError):
        return {}



def load_grid_cells(grid_cells_csv: Path) -> List[Dict[str, str]]:
    if not grid_cells_csv.exists():
        return []
    rows: List[Dict[str, str]] = []
    with grid_cells_csv.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows



def get_index_title(ndvi_meta: dict, grid_meta: dict) -> str:
    idx = (ndvi_meta.get("index", {}) or {}).get("index_name")
    if idx:
        return str(idx)
    idx2 = grid_meta.get("index_name")
    if idx2:
        return str(idx2)
    return "Vegetation Index"


def ensure_report_preview(source_path: Path, preview_path: Path) -> Path | None:
    if not source_path.exists():
        return None
    preview_path.parent.mkdir(parents=True, exist_ok=True)
    if source_path.suffix.lower() in {".tif", ".tiff"}:
        generated = _ensure_raster_preview(source_path, preview_path)
        if generated is not None:
            return generated
    try:
        with Image.open(source_path) as image:
            image.load()
            image.thumbnail((1400, 1400))
            image.convert("RGB").save(preview_path, format="PNG")
        return preview_path
    except (Image.DecompressionBombError, UnidentifiedImageError, OSError):
        return None


def _ensure_raster_preview(source_path: Path, preview_path: Path) -> Path | None:
    try:
        with rasterio.open(source_path) as src:
            width, height = _preview_size(src.width, src.height)
            indexes = [idx for idx in (1, 2, 3) if idx <= src.count]
            if not indexes:
                return None
            data = src.read(indexes, out_shape=(len(indexes), height, width), masked=True)
    except (OSError, rasterio.errors.RasterioIOError):
        return None

    Image.fromarray(_normalize_raster(data), mode="RGB").save(preview_path, format="PNG")
    return preview_path


def _preview_size(width: int, height: int) -> tuple[int, int]:
    scale = min(1.0, 1400.0 / float(max(width, height)))
    return max(1, int(round(width * scale))), max(1, int(round(height * scale)))


def _normalize_raster(data: np.ma.MaskedArray) -> np.ndarray:
    arr = np.ma.filled(data.astype("float32"), np.nan)
    if arr.shape[0] == 1:
        arr = np.repeat(arr, 3, axis=0)
    arr = arr[:3]

    out = np.zeros_like(arr, dtype="uint8")
    for idx, band in enumerate(arr):
        valid = np.isfinite(band)
        if not np.any(valid):
            continue
        low, high = np.nanpercentile(band[valid], [2, 98])
        if high <= low:
            low = float(np.nanmin(band[valid]))
            high = float(np.nanmax(band[valid]))
        if high <= low:
            continue
        scaled = np.clip((band - low) / (high - low) * 255.0, 0, 255)
        out[idx] = np.nan_to_num(scaled, nan=0.0).astype("uint8")

    return np.moveaxis(out, 0, -1)
