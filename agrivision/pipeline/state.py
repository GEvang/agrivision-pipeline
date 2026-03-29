from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class PipelineFlags:
    run_resize_step: bool = False
    skip_odm: bool = False
    skip_odm_rgb: bool = False
    skip_odm_mapir: bool = False
    skip_ndvi: bool = False


VALID_EXTS = ('.jpg', '.jpeg', '.png', '.tif', '.tiff')


def folder_has_images(folder: Path) -> bool:
    return folder.exists() and any(p.is_file() and p.suffix.lower() in VALID_EXTS for p in folder.iterdir())
