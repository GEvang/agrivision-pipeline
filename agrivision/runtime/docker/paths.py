from __future__ import annotations

from pathlib import Path

from agrivision.pipeline.stages.odm import _resolve_odm_bind_source


def resolve_host_bind_source(project_root: Path) -> Path:
    return _resolve_odm_bind_source(project_root)
