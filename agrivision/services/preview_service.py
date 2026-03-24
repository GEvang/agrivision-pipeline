from __future__ import annotations

from pathlib import Path

from PIL import Image, UnidentifiedImageError


class PreviewService:
    def ensure_preview(self, artifact_path: Path, preview_path: Path) -> Path | None:
        if not artifact_path.exists():
            return None
        preview_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with Image.open(artifact_path) as image:
                image.load()
                image.thumbnail((1200, 1200))
                image.convert('RGB').save(preview_path, format='PNG')
            return preview_path
        except (UnidentifiedImageError, OSError):
            return None

    def preview_name_for(self, artifact_path: Path) -> str:
        return f'{artifact_path.stem}_preview.png'
