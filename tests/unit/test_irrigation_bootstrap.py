from agrivision.services.irrigation.bootstrap import (
    _count_eto_values,
    _extract_lat_lon_from_wkt,
    _summarize_eto_values,
)


def test_extract_lat_lon_from_point_wkt() -> None:
    assert _extract_lat_lon_from_wkt("POINT (35.2600 25.6000)") == (35.26, 25.6)


def test_count_and_summarize_jsonld_eto_values() -> None:
    payload = {
        "@graph": [
            {"resultTime": "2026-05-24", "hasSimpleResult": "3.5"},
            {"resultTime": "2026-05-25", "hasSimpleResult": "4.5"},
        ]
    }

    assert _count_eto_values(payload) == 2
    assert _summarize_eto_values(payload) == {
        "min_mm": 3.5,
        "max_mm": 4.5,
        "average_mm": 4.0,
        "dates": ["2026-05-24", "2026-05-25"],
    }
