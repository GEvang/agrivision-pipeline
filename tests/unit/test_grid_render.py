from __future__ import annotations

import numpy as np
import rasterio
from rasterio.transform import from_origin

from agrivision.pipeline.grid.render import save_grid_overlay


def test_save_grid_overlay_accepts_rgb_background(tmp_path):
    background_path = tmp_path / "rgb.tif"
    out_path = tmp_path / "overlay.png"

    rgb = np.zeros((3, 4, 4), dtype="uint8")
    rgb[0] = 200
    rgb[1] = np.arange(16, dtype="uint8").reshape(4, 4) * 10
    rgb[2] = 40

    with rasterio.open(
        background_path,
        "w",
        driver="GTiff",
        height=4,
        width=4,
        count=3,
        dtype=rgb.dtype,
        transform=from_origin(0, 4, 1, 1),
    ) as dst:
        dst.write(rgb)

    arr = np.array(
        [
            [0.1, 0.2, 0.3, 0.4],
            [0.2, 0.3, 0.4, 0.5],
            [0.3, 0.4, 0.5, 0.6],
            [0.4, 0.5, 0.6, 0.7],
        ],
        dtype="float32",
    )
    cells = [
        {
            "r0": 0,
            "r1": 4,
            "c0": 0,
            "c1": 4,
            "cell_id": "A1",
            "class": "good",
        }
    ]

    save_grid_overlay(
        arr,
        cells,
        np.array([0, 4]),
        np.array([0, 4]),
        out_path,
        background_path=background_path,
    )

    assert out_path.exists()
    assert out_path.stat().st_size > 0
