from __future__ import annotations

from pathlib import Path

VALID_EXTS = ('.jpg', '.jpeg', '.png', '.tif', '.tiff')


def folder_has_images(folder: Path) -> bool:
    return folder.exists() and any(p.is_file() and p.suffix.lower() in VALID_EXTS for p in folder.iterdir())
