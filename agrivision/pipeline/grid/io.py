"""Grid stage settings, metadata loading, and artifact writers."""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

from agrivision.config.settings import get_project_root, load_config


def get_grid_settings() -> dict[str, object]:
    config = load_config()
    project_root = get_project_root()

    ndvi_dir = project_root / config["paths"]["ndvi_output"]
    ndvi_tif = ndvi_dir / "ndvi.tif"
    ndvi_meta_json = ndvi_dir / "metadata.json"
    grid_png = ndvi_dir / "ndvi_grid_overlay.png"
    grid_table_csv = ndvi_dir / "ndvi_grid_cells.csv"
    grid_categories_csv = ndvi_dir / "ndvi_grid_categories.csv"
    grid_meta_json = ndvi_dir / "grid_metadata.json"

    return {
        "ndvi_dir": ndvi_dir,
        "ndvi_tif": ndvi_tif,
        "ndvi_meta_json": ndvi_meta_json,
        "grid_png": grid_png,
        "grid_table_csv": grid_table_csv,
        "grid_categories_csv": grid_categories_csv,
        "grid_meta_json": grid_meta_json,
        "grid_rows": int(config["ndvi"]["grid_rows"]),
        "grid_cols": int(config["ndvi"]["grid_cols"]),
        "poor_max_cfg": float(config["ndvi"]["poor_max"]),
        "medium_max_cfg": float(config["ndvi"]["medium_max"]),
    }



def load_index_identity(ndvi_meta_json: Path) -> Tuple[str, str, str]:
    """Return (index_name, index_mode, source_dataset) from metadata.json."""
    if ndvi_meta_json.exists():
        try:
            with ndvi_meta_json.open("r", encoding="utf-8") as f:
                meta = json.load(f)
            idx = meta.get("index", {}) or {}
            src = meta.get("source", {}) or {}
            return (
                str(idx.get("index_name", "Vegetation Index")),
                str(idx.get("index_mode", "unknown")),
                str(src.get("dataset", "Unknown")),
            )
        except Exception:
            pass
    return "Vegetation Index", "unknown", "Unknown"



def save_cell_table_csv(
    cells: List[Dict[str, object]],
    out_path: Path,
    index_name: str,
    index_mode: str,
) -> None:
    """Write the index-aware grid cell CSV."""
    out_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "cell_id",
        "row_label",
        "col_label",
        "mean_index",
        "mean_ndvi",
        "class",
        "index_name",
        "index_mode",
    ]

    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for cell in cells:
            mean_val = cell["mean_value"]
            mean_str = "" if mean_val is None else f"{float(mean_val):.4f}"
            writer.writerow(
                {
                    "cell_id": cell["cell_id"],
                    "row_label": cell["row_label"],
                    "col_label": cell["col_label"],
                    "mean_index": mean_str,
                    "mean_ndvi": mean_str,
                    "class": cell["class"],
                    "index_name": index_name,
                    "index_mode": index_mode,
                }
            )

    print(f"[OK] Cell table CSV saved to {out_path}")



def save_categories_csv(
    out_path: Path,
    poor_max: float,
    medium_max: float,
    index_name: str,
    index_mode: str,
) -> None:
    """Write the class threshold CSV used by the grid stage."""
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "class",
                "threshold_min",
                "threshold_max",
                "index_name",
                "index_mode",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "class": "poor",
                "threshold_min": -1.0,
                "threshold_max": float(poor_max),
                "index_name": index_name,
                "index_mode": index_mode,
            }
        )
        writer.writerow(
            {
                "class": "medium",
                "threshold_min": float(poor_max),
                "threshold_max": float(medium_max),
                "index_name": index_name,
                "index_mode": index_mode,
            }
        )
        writer.writerow(
            {
                "class": "good",
                "threshold_min": float(medium_max),
                "threshold_max": 1.0,
                "index_name": index_name,
                "index_mode": index_mode,
            }
        )
        writer.writerow(
            {
                "class": "no_data",
                "threshold_min": "",
                "threshold_max": "",
                "index_name": index_name,
                "index_mode": index_mode,
            }
        )

    print(f"[OK] Categories CSV saved to {out_path}")



def save_grid_metadata(
    out_path: Path,
    index_name: str,
    index_mode: str,
    source_dataset: str,
    classification_mode: str,
    poor_max_used: float,
    medium_max_used: float,
    grid_rows: int,
    grid_cols: int,
    poor_max_cfg: float,
    medium_max_cfg: float,
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "generated_at_utc": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "index_name": index_name,
        "index_mode": index_mode,
        "source_dataset": source_dataset,
        "grid": {"rows": grid_rows, "cols": grid_cols},
        "classification_mode": classification_mode,
        "thresholds_used": {
            "poor_max": float(poor_max_used),
            "medium_max": float(medium_max_used),
        },
        "thresholds_configured": {
            "poor_max": float(poor_max_cfg),
            "medium_max": float(medium_max_cfg),
        },
    }

    with out_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print(f"[OK] Grid metadata saved to {out_path}")
