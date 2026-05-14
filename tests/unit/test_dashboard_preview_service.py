from __future__ import annotations

from pathlib import Path

import numpy as np
import rasterio
from PIL import Image
from rasterio.transform import from_origin

from agrivision.services.preview_service import PreviewService


def test_preview_service_creates_preview(tmp_path: Path) -> None:
    source = tmp_path / 'ortho.tif'
    preview = tmp_path / 'preview.png'
    Image.new('RGB', (64, 64)).save(source)
    service = PreviewService()
    generated = service.ensure_preview(source, preview)
    assert generated == preview
    assert preview.exists()


def test_preview_service_creates_geotiff_preview_with_rasterio(tmp_path: Path) -> None:
    source = tmp_path / 'ortho.tif'
    preview = tmp_path / 'preview.png'
    data = np.zeros((3, 32, 32), dtype='uint8')
    data[0] = 120
    data[1] = np.arange(32, dtype='uint8').reshape(1, 32)
    data[2] = 40

    with rasterio.open(
        source,
        'w',
        driver='GTiff',
        height=32,
        width=32,
        count=3,
        dtype=data.dtype,
        transform=from_origin(0, 32, 1, 1),
    ) as dst:
        dst.write(data)

    service = PreviewService()
    generated = service.ensure_preview(source, preview)

    assert generated == preview
    assert preview.exists()


def test_preview_service_normalizes_masked_uint8_raster() -> None:
    data = np.ma.array(
        np.array(
            [
                [[0, 50], [100, 150]],
                [[10, 60], [110, 160]],
                [[20, 70], [120, 170]],
            ],
            dtype='uint8',
        ),
        mask=[
            [[False, False], [False, True]],
            [[False, False], [False, True]],
            [[False, False], [False, True]],
        ],
    )

    image = PreviewService()._normalize_raster(data)

    assert image.shape == (2, 2, 3)
    assert image.dtype == np.uint8
