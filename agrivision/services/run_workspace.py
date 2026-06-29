from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agrivision.app.schemas.runs import RunRecord
from agrivision.config import load_config
from agrivision.pipeline.io.paths import resolve_pipeline_paths
from agrivision.services.storage_service import StorageService


@dataclass(frozen=True)
class RunWorkspace:
    run_id: str
    root: Path
    config: dict[str, Any]
    project_root: Path
    output_root: Path
    ndvi_output: Path
    images_full_rgb: Path
    images_resized_rgb: Path
    images_full_mapir: Path
    images_resized_mapir: Path
    images_full_thermal: Path
    images_resized_thermal: Path
    odm_project_root_rgb: Path
    odm_project_root_mapir: Path
    odm_project_root_thermal: Path
    ortho_rgb: Path
    ortho_mapir: Path
    ortho_thermal: Path
    report_path: Path

    @classmethod
    def from_run_record(cls, record: RunRecord, storage: StorageService) -> RunWorkspace:
        config = load_config()
        root = storage.run_dir(record.run_id) / 'workspace'
        resolved = resolve_pipeline_paths(workspace_root=root, config=config)
        return cls(
            run_id=record.run_id,
            root=root,
            config=config,
            project_root=resolved['project_root'],
            output_root=resolved['output_root'],
            ndvi_output=resolved['ndvi_output'],
            images_full_rgb=resolved['images_full_rgb'],
            images_resized_rgb=resolved['images_resized_rgb'],
            images_full_mapir=resolved['images_full_mapir'],
            images_resized_mapir=resolved['images_resized_mapir'],
            images_full_thermal=resolved['images_full_thermal'],
            images_resized_thermal=resolved['images_resized_thermal'],
            odm_project_root_rgb=resolved['odm_project_root_rgb'],
            odm_project_root_mapir=resolved['odm_project_root_mapir'],
            odm_project_root_thermal=resolved['odm_project_root_thermal'],
            ortho_rgb=resolved['ortho_rgb'],
            ortho_mapir=resolved['ortho_mapir'],
            ortho_thermal=resolved['ortho_thermal'],
            report_path=resolved['report_path'],
        )
