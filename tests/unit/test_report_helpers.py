from pathlib import Path

from agrivision.pipeline.report.assets import get_index_title
from agrivision.pipeline.report.sections import render_weather_section
from agrivision.pipeline.report.tables import render_grid_table


def test_get_index_title_prefers_metadata_index_name() -> None:
    ndvi_meta = {"index": {"index_name": "GNDVI-like"}}
    grid_meta = {"index_name": "Vegetation Index"}
    assert get_index_title(ndvi_meta, grid_meta) == "GNDVI-like"



def test_render_grid_table_uses_mean_index_and_class() -> None:
    html = render_grid_table(
        "Vegetation Index",
        [{
            "cell_id": "A1",
            "row_label": "A",
            "col_label": "1",
            "mean_index": "0.4321",
            "class": "good",
        }],
    )
    assert "A1" in html
    assert "0.4321" in html
    assert "class-good" in html



def test_render_weather_section_includes_weather_heading() -> None:
    html = render_weather_section(
        {
            "enabled": True,
            "location_name": "Neapolis",
            "current_weather": {
                "timestamp": "2026-03-20T07:00:00+00:00",
                "temperature": 18.2,
                "humidity": 66,
                "wind_speed": 3.4,
                "pressure": 1008,
                "description": "clear sky",
            },
            "forecast5_points": [
                {
                    "timestamp": "2026-03-20T09:00:00+00:00",
                    "measurement_type": "temperature",
                    "value": 19.1,
                    "source": "openweather",
                }
            ],
            "thi": {"value": 68.1},
            "thi_jsonld": {"@context": {}},
            "forecast5_jsonld": {"@graph": []},
            "uav_flight_forecast": {"data": [{"status": "good"}]},
            "spray_forecast": {"data": [{"status": "caution"}]},
            "spray_forecast_jsonld": {"@graph": []},
            "historical_daily": {"data": [{"date": "2026-03-19"}]},
            "historical_hourly": {"data": [{"time": "2026-03-19T12:00:00"}]},
            "notes": [],
            "uav_model": "dji_phantom4",
            "history_start_date": "2026-03-17",
            "history_end_date": "2026-03-20",
        },
        Path("output"),
    )
    assert "OpenAgri Weather Service" in html
    assert "Current Weather Conditions" in html
    assert "Spray Condition Forecast" in html
