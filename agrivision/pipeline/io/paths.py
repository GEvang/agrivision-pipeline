from __future__ import annotations

from pathlib import Path
from typing import Any

from agrivision.config import get_project_root, load_config


def resolve_pipeline_paths() -> dict[str, Path | dict[str, Any]]:
    config = load_config()
    project_root = get_project_root()
    paths = config["paths"]
    return {
        "config": config,
        "project_root": project_root,
        "output_root": project_root / paths["output_root"],
        "ndvi_output": project_root / paths["ndvi_output"],
        "ortho_rgb": project_root / paths["odm_project_root_rgb"] / "project/odm_orthophoto/odm_orthophoto.tif",
        "ortho_mapir": project_root / paths["odm_project_root_mapir"] / "project/odm_orthophoto/odm_orthophoto.tif",
        "ortho_thermal": project_root / paths["odm_project_root_thermal"] / "project/odm_orthophoto/odm_orthophoto.tif",
        "images_full_rgb": project_root / paths["images_full"],
        "images_resized_rgb": project_root / paths["images_resized"],
        "images_full_mapir": project_root / paths["images_full_mapir"],
        "images_resized_mapir": project_root / paths["images_resized_mapir"],
        "images_full_thermal": project_root / paths["images_full_thermal"],
        "images_resized_thermal": project_root / paths["images_resized_thermal"],
    }
