from __future__ import annotations

import shutil

from agrivision.config import get_project_root, load_config


def cleanup_outputs() -> list[str]:
    config = load_config()
    project_root = get_project_root()
    removed: list[str] = []
    for relative in [config['paths']['ndvi_output'], config['paths']['runs_output']]:
        path = project_root / relative
        if path.exists():
            shutil.rmtree(path)
            removed.append(str(path))
    return removed
