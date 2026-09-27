from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin

from agrivision.pipeline.io import geolocation


def _geotiff(path: Path) -> None:
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=4,
        width=4,
        count=1,
        dtype="uint8",
        crs="EPSG:4326",
        transform=from_origin(25.0, 36.0, 0.1, 0.1),
    ) as dataset:
        dataset.write(np.ones((1, 4, 4), dtype="uint8"))


def test_resolves_run_location_from_geotiff_and_reverse_geocoder(monkeypatch, tmp_path: Path) -> None:
    orthophoto = tmp_path / "rgb.tif"
    _geotiff(orthophoto)

    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"address": {"village": "Vederi", "county": "Rethymno"}}

    monkeypatch.setattr(geolocation.requests, "get", lambda *args, **kwargs: Response())

    location = geolocation.resolve_orthophoto_location([orthophoto])

    assert location is not None
    assert location["label"] == "Vederi, Rethymno"
    assert location["geocoded"] is True
    assert location["latitude"] == 35.8
    assert location["longitude"] == 25.2


def test_geotiff_location_falls_back_to_coordinates_when_geocoder_is_unavailable(monkeypatch, tmp_path: Path) -> None:
    orthophoto = tmp_path / "thermal.tif"
    _geotiff(orthophoto)

    monkeypatch.setattr(geolocation, "_reverse_geocode", lambda *_args: None)

    location = geolocation.resolve_orthophoto_location([orthophoto])

    assert location is not None
    assert location["label"] == "35.80000, 25.20000"
    assert location["geocoded"] is False
