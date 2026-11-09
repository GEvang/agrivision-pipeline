from __future__ import annotations

import csv
import json
from pathlib import Path

from agrivision.pipeline.risk.scoring import run_disease_risk_scoring
from agrivision.pipeline.stages.disease_risk import run_disease_risk


def _write_grid(vegetation_index_dir: Path) -> None:
    vegetation_index_dir.mkdir(parents=True, exist_ok=True)
    rows = [
        ("A1", "A", "1", "0.80", "1.0", 0, 50, 0, 50),
        ("A2", "A", "2", "0.30", "1.0", 0, 50, 50, 100),
        ("B1", "B", "1", "0.60", "1.0", 50, 100, 0, 50),
        ("B2", "B", "2", "0.10", "1.0", 50, 100, 50, 100),
    ]
    with (vegetation_index_dir / "vegetation_index_grid_cells.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "cell_id",
                "row_label",
                "col_label",
                "mean_index",
                "valid_fraction",
                "r0",
                "r1",
                "c0",
                "c1",
            ]
        )
        writer.writerows(rows)
    (vegetation_index_dir / "grid_metadata.json").write_text(
        json.dumps({"generated_at_utc": "2026-05-18T10:00:00Z", "grid": {"rows": 2, "cols": 2}}),
        encoding="utf-8",
    )
    (vegetation_index_dir / "metadata.json").write_text(
        json.dumps({"generated_at_utc": "2026-05-18T10:00:00Z"}),
        encoding="utf-8",
    )


def test_disease_risk_scoring_writes_layers(tmp_path: Path) -> None:
    vegetation_index_dir = tmp_path / "vegetation_index"
    _write_grid(vegetation_index_dir)

    summary = run_disease_risk_scoring(
        crop="grapevine",
        vegetation_index_dir=vegetation_index_dir,
        rgb_orthophoto=tmp_path / "missing_rgb.tif",
        weather_summary={
            "current_weather": {
                "timestamp": "2026-05-18T10:00:00Z",
                "temperature": 22,
                "humidity": 72,
                "wind_speed": 2.5,
                "raw": {"rain": {"1h": 0.4}},
            }
        },
        irrigation_summary={"authenticated": True, "eto": {"ok": True}},
    )

    assert summary["enabled"] is True
    assert summary["selected_layer_key"]
    assert len(summary["layers"]) == 3
    assert (vegetation_index_dir / "disease_risk" / "summary.json").exists()

    selected = next(layer for layer in summary["layers"] if layer["profile_key"] == summary["selected_layer_key"])
    assert selected["seasonality_score"] > 0
    assert selected["weather_suitability"] is not None
    assert "vegetation_index_anomaly" in selected["used_inputs"]
    assert Path(selected["cells_csv"]).exists()
    assert Path(selected["overlay_png"]).exists()


def test_disease_risk_stage_uses_the_current_run_workspace(tmp_path: Path) -> None:
    _write_grid(tmp_path / "output" / "vegetation_index")
    config = {
        "paths": {
            "output_root": "output",
            "vegetation_index_output": "output/vegetation_index",
            "images_full": "data/rgb",
            "images_full_mapir": "data/mapir",
            "images_full_thermal": "data/thermal",
            "odm_project_root_rgb": "data/odm_rgb",
            "odm_project_root_mapir": "data/odm_mapir",
            "odm_project_root_thermal": "data/odm_thermal",
        }
    }

    summary = run_disease_risk(
        crop="grapevine",
        weather_summary={"current_weather": {"timestamp": "2026-05-18T10:00:00Z", "temperature": 22, "humidity": 72, "wind_speed": 2.5, "raw": {"rain": {"1h": 0.4}}}},
        irrigation_summary=None,
        pdm_summary={"risk_level": "Moderate", "selected_model_key": "grapevine_powdery_mildew_risk_v1"},
        workspace_root=tmp_path,
        config=config,
    )

    assert len(summary["layers"]) == 3
    assert summary["field_assessment"]["status"] == "Medium"
    assert (tmp_path / "output" / "vegetation_index" / "disease_risk" / "summary.json").exists()


def test_zero_rain_is_a_measurement_not_missing() -> None:
    from agrivision.pipeline.risk.scoring import _extract_weather_values

    values = _extract_weather_values(
        {
            "current_weather": {"raw": {"rain": {"1h": 0.0}}},
            "historical_hourly": {"data": [{"timestamp": "2026-05-17T10:00:00Z", "values": {"precipitation": 9.0}}]},
        }
    )

    assert values["precipitation"] == 0.0


def test_past_flight_uses_flight_day_history_not_current_weather() -> None:
    from datetime import date

    from agrivision.pipeline.risk.scoring import resolve_weather_values

    weather = {
        "current_weather": {"temperature": 5.0, "humidity": 30.0, "wind_speed": 9.0},
        "historical_hourly": {
            "data": [
                {"timestamp": "2026-05-17T12:00:00", "values": {"temperature_2m": 18.0, "relative_humidity_2m": 60.0, "precipitation": 1.0}},
                {"timestamp": "2026-05-18T09:00:00", "values": {"temperature_2m": 20.0, "relative_humidity_2m": 80.0, "precipitation": 0.5}},
                {"timestamp": "2026-05-18T15:00:00", "values": {"temperature_2m": 24.0, "relative_humidity_2m": 70.0, "precipitation": 0.0}},
            ]
        },
    }

    values, basis = resolve_weather_values(weather, date(2026, 5, 18))
    missing, missing_basis = resolve_weather_values(weather, date(2026, 4, 1))

    assert basis == "history"
    assert values == {"temperature": 22.0, "humidity": 75.0, "wind_speed": None, "precipitation": 1.5}
    assert missing_basis == "unavailable"
    assert all(value is None for value in missing.values())


def test_flight_date_sets_season_and_reports_ceiling(tmp_path: Path) -> None:
    from datetime import date

    vegetation_index_dir = tmp_path / "vegetation_index"
    _write_grid(vegetation_index_dir)

    summary = run_disease_risk_scoring(
        crop="grapevine",
        vegetation_index_dir=vegetation_index_dir,
        rgb_orthophoto=tmp_path / "missing_rgb.tif",
        weather_summary={"current_weather": {"timestamp": "2026-11-09T10:00:00Z"}},
        irrigation_summary=None,
        flight_date=date(2026, 5, 18),
    )

    assert summary["capture_month_used"] == 5
    assert summary["capture_month_source"] == "flight_date"
    assert summary["weather_basis"] == "unavailable"
    layer = summary["layers"][0]
    assert layer["max_reachable_risk"] <= 0.2 + 1e-9  # only the index anomaly driver is available
    assert any("cannot exceed" in note for note in summary["notes"])
    assert any("not available" in note for note in summary["notes"])


def test_used_inputs_looks_past_a_first_cell_without_data(tmp_path: Path) -> None:
    vegetation_index_dir = tmp_path / "vegetation_index"
    _write_grid(vegetation_index_dir)
    grid_csv = vegetation_index_dir / "vegetation_index_grid_cells.csv"
    grid_csv.write_text(grid_csv.read_text(encoding="utf-8").replace("A1,A,1,0.80", "A1,A,1,"), encoding="utf-8")

    summary = run_disease_risk_scoring(
        crop="grapevine",
        vegetation_index_dir=vegetation_index_dir,
        rgb_orthophoto=tmp_path / "missing_rgb.tif",
        weather_summary={},
        irrigation_summary=None,
    )

    assert "vegetation_index_anomaly" in summary["layers"][0]["used_inputs"]
