"""Generate disease and pest risk layers from grid, weather, and context data."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agrivision.pipeline.io.paths import resolve_pipeline_paths
from agrivision.pipeline.risk.assessment import build_field_assessment
from agrivision.pipeline.risk.scoring import run_disease_risk_scoring


def run_disease_risk(
    *,
    crop: str | None,
    weather_summary: dict[str, Any],
    irrigation_summary: dict[str, Any] | None,
    pdm_summary: dict[str, Any] | None = None,
    workspace_root: Path | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    resolved = resolve_pipeline_paths(workspace_root=workspace_root, config=config)
    vegetation_index_dir = resolved["vegetation_index_output"]
    rgb_orthophoto = resolved["ortho_rgb"]
    print("\n[AgriVision] Disease risk scoring...")
    summary = run_disease_risk_scoring(
        crop=crop,
        vegetation_index_dir=vegetation_index_dir,
        rgb_orthophoto=Path(rgb_orthophoto),
        weather_summary=weather_summary,
        irrigation_summary=irrigation_summary,
    )
    summary["field_assessment"] = build_field_assessment(summary, pdm_summary)
    summary_path_value = summary.get("summary_json")
    if summary_path_value:
        Path(str(summary_path_value)).write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"[AgriVision] Disease risk layers generated: {len(summary.get('layers', []))}")
    return summary
