"""Generate disease and pest risk layers from grid, weather, and context data."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agrivision.config.settings import get_project_root, load_config
from agrivision.pipeline.risk.scoring import run_disease_risk_scoring


def run_disease_risk(
    *,
    crop: str | None,
    weather_summary: dict[str, Any],
    irrigation_summary: dict[str, Any] | None,
) -> dict[str, Any]:
    config = load_config()
    project_root = get_project_root()
    paths = config["paths"]
    vegetation_index_dir = project_root / paths["vegetation_index_output"]
    rgb_orthophoto = (
        project_root
        / paths["odm_project_root_rgb"]
        / "project"
        / "odm_orthophoto"
        / "odm_orthophoto.tif"
    )
    print("\n[AgriVision] Disease risk scoring...")
    summary = run_disease_risk_scoring(
        crop=crop,
        vegetation_index_dir=vegetation_index_dir,
        rgb_orthophoto=Path(rgb_orthophoto),
        weather_summary=weather_summary,
        irrigation_summary=irrigation_summary,
    )
    print(f"[AgriVision] Disease risk layers generated: {len(summary.get('layers', []))}")
    return summary
