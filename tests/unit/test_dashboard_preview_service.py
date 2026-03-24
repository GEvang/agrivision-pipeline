from __future__ import annotations

from pathlib import Path

from PIL import Image

from agrivision.services.preview_service import PreviewService


def test_preview_service_creates_preview(tmp_path: Path) -> None:
    source = tmp_path / 'ortho.tif'
    preview = tmp_path / 'preview.png'
    Image.new('RGB', (64, 64)).save(source)
    service = PreviewService()
    generated = service.ensure_preview(source, preview)
    assert generated == preview
    assert preview.exists()
