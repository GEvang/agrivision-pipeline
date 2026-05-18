from pathlib import Path

from agrivision.pipeline.report.assets import get_index_title
from agrivision.pipeline.report.html import build_report_html
from agrivision.pipeline.report.sections import render_weather_section
from agrivision.pipeline.report.tables import render_grid_table


def test_get_index_title_prefers_metadata_index_name() -> None:
    ndvi_meta = {"index": {"index_name": "Vegetation Index"}}
    grid_meta = {"index_name": "Fallback Index"}
    assert get_index_title(ndvi_meta, grid_meta) == "Vegetation Index"



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
            "notes": [],
            "history_start_date": "2026-03-17",
            "history_end_date": "2026-03-20",
        },
        Path("output"),
    )
    assert "OpenAgri Weather Service" in html
    assert "Current Weather Conditions" in html
    assert "5-Day Forecast Preview" in html
    assert "Spray Condition Forecast" not in html
    assert "Forecast JSON-LD / OCSM Preview" not in html
    assert "UAV model" not in html


def test_build_report_html_uses_risk_mapping_layout() -> None:
    html = build_report_html(
        generated_at="2026-05-18 12:00 UTC",
        index_title="Vegetation Index",
        weather_html="<section>Weather</section>",
        methodology_html="<section>Method</section>",
        artifacts_list_html="<li>Artifact</li>",
        visible_image_html='<img src="visible.png" alt="Visible" />',
        ndvi_color_html='<img src="ndvi.png" alt="NDVI" />',
        thermal_image_html='<img src="mapir.png" alt="MAPIR placeholder" />',
        grid_meta_html="<table><tr><td>Grid</td></tr></table>",
        grid_overlay_html='<img src="grid.png" alt="Risk grid" />',
        grid_table_html="<table><tr><td>A1</td></tr></table>",
        irrigation_html="<section>Irrigation</section>",
        pdm_html="<section>PDM</section>",
    )

    assert "Field Analysis and Risk Mapping" in html
    assert "Visible Orthomosaic" in html
    assert "Thermal" in html
    assert "MAPIR placeholder until thermal imagery is available" in html
    assert "Risk Index" in html
    assert "Detailed Analysis" in html
    assert '<svg class="svg-icon' in html
