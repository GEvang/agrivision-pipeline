from __future__ import annotations

from pathlib import Path
from typing import Any

from agrivision.config import get_project_root, load_config


def resolve_pipeline_paths(
    workspace_root: Path | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Path | dict[str, Any]]:
    resolved_config = config or load_config()
    project_root = workspace_root.resolve() if workspace_root is not None else get_project_root()
    paths = resolved_config["paths"]
    return {
        "config": resolved_config,
        "project_root": project_root,
        "output_root": project_root / paths["output_root"],
        "ndvi_output": project_root / paths["ndvi_output"],
        "images_full_rgb": project_root / paths["images_full"],
        "images_resized_rgb": project_root / paths["images_resized"],
        "ortho_rgb": project_root / paths["odm_project_root_rgb"] / "project/odm_orthophoto/odm_orthophoto.tif",
        "ortho_mapir": project_root / paths["odm_project_root_mapir"] / "project/odm_orthophoto/odm_orthophoto.tif",
        "odm_project_root_rgb": project_root / paths["odm_project_root_rgb"],
        "odm_project_root_mapir": project_root / paths["odm_project_root_mapir"],
        "images_full_mapir": project_root / paths["images_full_mapir"],
        "images_resized_mapir": project_root / paths["images_resized_mapir"],
        "report_path": project_root / paths["output_root"] / "report_latest.html",
    }
