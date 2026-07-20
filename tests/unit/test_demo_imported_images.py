from __future__ import annotations

import asyncio
from io import BytesIO
from pathlib import Path

from fastapi import UploadFile
from PIL import Image

from agrivision.app.routes import uploads
from agrivision.app.routes.uploads import _store_imported_orthophoto


def test_store_imported_orthophoto_accepts_png_and_converts_to_tiff(tmp_path: Path) -> None:
    buffer = BytesIO()
    Image.new('RGB', (24, 24), color=(20, 30, 40)).save(buffer, format='PNG')
    buffer.seek(0)
    upload = UploadFile(filename='demo.png', file=buffer)

    path, errors = asyncio.run(_store_imported_orthophoto('rgb', upload, tmp_path))

    assert errors == []
    assert path is not None
    assert path.endswith('orthophoto_rgb.tif')
    assert Path(path).exists()


def test_store_imported_orthophoto_uses_project_pixel_limit(tmp_path: Path, monkeypatch) -> None:
    buffer = BytesIO()
    Image.new('RGB', (20, 20), color=(20, 30, 40)).save(buffer, format='PNG')
    buffer.seek(0)
    upload = UploadFile(filename='large-demo.png', file=buffer)
    original_max_pixels = Image.MAX_IMAGE_PIXELS
    monkeypatch.setattr(Image, 'MAX_IMAGE_PIXELS', 100)
    monkeypatch.setattr(uploads, 'MAX_IMAGE_PIXELS', 500)

    try:
        path, errors = asyncio.run(_store_imported_orthophoto('rgb', upload, tmp_path))
    finally:
        Image.MAX_IMAGE_PIXELS = original_max_pixels

    assert errors == []
    assert path is not None
    assert Path(path).exists()
