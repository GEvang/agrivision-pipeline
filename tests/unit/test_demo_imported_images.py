from __future__ import annotations

import asyncio
from io import BytesIO
from pathlib import Path

from fastapi import UploadFile
from PIL import Image

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
