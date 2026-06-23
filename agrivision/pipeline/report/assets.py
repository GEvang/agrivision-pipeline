"""Asset discovery and data loading helpers for the HTML report stage."""

from __future__ import annotations

import csv
import json
from json import JSONDecodeError
from pathlib import Path
from typing import Any, Dict, List

from agrivision.pipeline.io.paths import resolve_pipeline_paths


def get_report_settings(
    workspace_root: Path | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Path]:
    resolved = resolve_pipeline_paths(workspace_root=workspace_root, config=config)
    output_dir = resolved["output_root"]
    report_path = resolved["report_path"]
    ndvi_dir = resolved["ndvi_output"]
    weather_dir = output_dir / "weather"
    return {
        "output_dir": output_dir,
        "report_path": report_path,
        "ndvi_dir": ndvi_dir,
        "weather_dir": weather_dir,
        "ndvi_meta_path": ndvi_dir / "metadata.json",
        "grid_meta_path": ndvi_dir / "grid_metadata.json",
        "ndvi_tif": ndvi_dir / "ndvi.tif",
        "ndvi_color_png": ndvi_dir / "ndvi_color.png",
        "grid_overlay_png": ndvi_dir / "ndvi_grid_overlay.png",
        "grid_cells_csv": ndvi_dir / "ndvi_grid_cells.csv",
        "grid_categories_csv": ndvi_dir / "ndvi_grid_categories.csv",
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
