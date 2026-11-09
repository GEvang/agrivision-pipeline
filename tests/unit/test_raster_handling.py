from __future__ import annotations

import numpy as np
import rasterio
from rasterio.enums import ColorInterp
from rasterio.transform import from_origin

from agrivision.integrations.common.geometry import (
    openagri_point_wkt,
    parse_openagri_point_wkt,
)
from agrivision.pipeline.stages import grid as grid_stage
from agrivision.pipeline.stages.vegetation_index import compute_index


def test_openagri_point_wkt_is_latitude_first() -> None:
    # The OpenAgri services read centroid.x as latitude.
    wkt = openagri_point_wkt(35.26, 25.6)

    assert wkt == "POINT (35.2600000 25.6000000)"
    assert parse_openagri_point_wkt(wkt) == (35.26, 25.6)
    assert parse_openagri_point_wkt("POLYGON ((1 2, 3 4, 1 2))") is None


def test_grid_reads_large_index_at_bounded_resolution(monkeypatch, tmp_path) -> None:
    path = tmp_path / "index.tif"
    values = np.zeros((40, 40), dtype="float32")
    values[:, 20:] = 1.0
    with rasterio.open(
        path, "w", driver="GTiff", height=40, width=40, count=1, dtype="float32",
        nodata=np.nan, transform=from_origin(100, 200, 0.5, 0.5), crs="EPSG:32635",
    ) as dst:
        dst.write(values, 1)
    monkeypatch.setattr(grid_stage, "MAX_ANALYSIS_PIXELS", 100)

    arr, transform, crs, scale = grid_stage._read_index_for_analysis(path)

    assert arr.shape == (10, 10)
    assert scale == 0.25
    assert transform.a == 2.0 and transform.c == 100
    assert np.allclose(arr[:, :5], 0.0) and np.allclose(arr[:, 5:], 1.0)
    assert crs.to_epsg() == 32635


def test_rgb_mask_scaling_brings_16bit_onto_8bit_range() -> None:
    rgb = np.full((3, 2, 2), 40000.0, dtype="float32")

    scaled = grid_stage._scale_rgb_to_8bit(rgb, "uint16")
    unchanged = grid_stage._scale_rgb_to_8bit(np.full((3, 2, 2), 120.0, dtype="float32"), "uint8")

    assert float(scaled.max()) <= 255.0
    assert float(unchanged.max()) == 120.0


def _write_four_band(path, *, alpha: bool) -> None:
    bands = np.zeros((4, 4, 4), dtype="uint8")
    bands[0] = 40   # red
    bands[1] = 80   # green
    bands[2] = 60   # blue
    bands[3] = 0 if alpha else 200  # alpha (transparent) or a NIR band
    with rasterio.open(
        path, "w", driver="GTiff", height=4, width=4, count=4, dtype="uint8",
        transform=from_origin(0, 4, 1, 1), crs="EPSG:32635",
    ) as dst:
        dst.write(bands)
        if alpha:
            dst.colorinterp = [ColorInterp.red, ColorInterp.green, ColorInterp.blue, ColorInterp.alpha]


def test_fourth_spectral_band_is_not_treated_as_alpha(tmp_path) -> None:
    path = tmp_path / "rgbn.tif"
    _write_four_band(path, alpha=False)
    profile = {"index_mode": "nir_red", "nir_band": 4, "red_band": 1}

    with rasterio.open(path) as src:
        index, _ = compute_index(src, "MAPIR", profile)

    assert np.isfinite(index).all()
    assert np.allclose(index, (200 - 40) / (200 + 40))


def test_real_alpha_band_masks_transparent_pixels(tmp_path) -> None:
    path = tmp_path / "rgba.tif"
    _write_four_band(path, alpha=True)
    profile = {"index_mode": "pseudo", "nir_band": 2, "red_band": 1}

    with rasterio.open(path) as src:
        index, _ = compute_index(src, "RGB", profile)

    assert not np.isfinite(index).any()
