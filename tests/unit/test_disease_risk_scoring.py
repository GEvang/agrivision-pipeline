from __future__ import annotations

import csv
import json
from pathlib import Path

from agrivision.pipeline.risk.scoring import run_disease_risk_scoring


def _write_grid(ndvi_dir: Path) -> None:
    ndvi_dir.mkdir(parents=True, exist_ok=True)
    rows = [
        ("A1", "A", "1", "0.80", "1.0", 0, 50, 0, 50),
        ("A2", "A", "2", "0.30", "1.0", 0, 50, 50, 100),
        ("B1", "B", "1", "0.60", "1.0", 50, 100, 0, 50),
        ("B2", "B", "2", "0.10", "1.0", 50, 100, 50, 100),
    ]
    with (ndvi_dir / "ndvi_grid_cells.csv").open("w", newline="", encoding="utf-8") as handle:
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
    (ndvi_dir / "grid_metadata.json").write_text(
        json.dumps({"generated_at_utc": "2026-05-18T10:00:00Z", "grid": {"rows": 2, "cols": 2}}),
        encoding="utf-8",
    )
    (ndvi_dir / "metadata.json").write_text(
        json.dumps({"generated_at_utc": "2026-05-18T10:00:00Z"}),
        encoding="utf-8",
    )


def test_disease_risk_scoring_writes_layers(tmp_path: Path) -> None:
    ndvi_dir = tmp_path / "ndvi"
    _write_grid(ndvi_dir)

    summary = run_disease_risk_scoring(
        crop="grapevine",
        ndvi_dir=ndvi_dir,
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
    assert (ndvi_dir / "disease_risk" / "summary.json").exists()

    selected = next(layer for layer in summary["layers"] if layer["profile_key"] == summary["selected_layer_key"])
    assert selected["seasonality_score"] > 0
    assert selected["weather_suitability"] is not None
    assert "ndvi_anomaly" in selected["used_inputs"]
    assert Path(selected["cells_csv"]).exists()
    assert Path(selected["overlay_png"]).exists()
