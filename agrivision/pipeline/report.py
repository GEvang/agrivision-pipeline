#!/usr/bin/env python3
"""
agrivision.pipeline.report

Generate a static HTML farmer report that combines:

- Latest NDVI color image
- NDVI basic statistics (min / max / mean)
- NDVI grid overlay and links to CSV tables
- Current weather from the OpenAgri WeatherService
- A table of all grid cells (ID, NDVI, class)
"""

from __future__ import annotations

from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List

import csv
import numpy as np
import rasterio

from agrivision.utils.settings import get_project_root, load_config
from agrivision.weather.client import fetch_current_weather


CONFIG = load_config()
PROJECT_ROOT = get_project_root()

NDVI_DIR = PROJECT_ROOT / CONFIG["paths"]["ndvi_output"]
OUTPUT_ROOT = PROJECT_ROOT / CONFIG["paths"]["output_root"]

NDVI_TIF = NDVI_DIR / "ndvi.tif"
NDVI_COLOR_PNG = NDVI_DIR / "ndvi_color.png"
NDVI_GRID_PNG = NDVI_DIR / "ndvi_grid_overlay.png"
NDVI_GRID_CELLS_CSV = NDVI_DIR / "ndvi_grid_cells.csv"
NDVI_GRID_CATEGORIES_CSV = NDVI_DIR / "ndvi_grid_categories.csv"

REPORT_HTML = OUTPUT_ROOT / "report_latest.html"


def _fmt(value: float | None, digits: int = 3) -> str:
    if value is None or not np.isfinite(value):
        return "N/A"
    return f"{value:.{digits}f}"


def read_ndvi_stats() -> Dict[str, Any]:
    if not NDVI_TIF.exists():
        return {"available": False, "min": None, "max": None, "mean": None}

    with rasterio.open(NDVI_TIF) as src:
        arr = src.read(1).astype("float32")

    arr[~np.isfinite(arr)] = np.nan

    if np.all(np.isnan(arr)):
        return {"available": False, "min": None, "max": None, "mean": None}

    return {
        "available": True,
        "min": float(np.nanmin(arr)),
        "max": float(np.nanmax(arr)),
        "mean": float(np.nanmean(arr)),
    }


def build_weather_context() -> Dict[str, Any]:
    """
    Fetch current weather from OpenAgri WeatherService.
    If anything fails, return a minimal context with 'N/A' values so that
    the report can still be generated.
    """
    try:
        cw = fetch_current_weather()
    except Exception as e:
        print(f"[Weather] WARNING: could not fetch weather data: {e}")
        return {
            "location_name": "Weather service unavailable",
            "time_local": "N/A",
            "temp_c": "N/A",
            "humidity": "N/A",
            "pressure_hpa": "N/A",
            "wind_speed": "N/A",
            "description": "Weather data not available.",
        }

    ts_str = cw.timestamp.strftime("%Y-%m-%d %H:%M") if cw.timestamp else "N/A"

    return {
        "location_name": cw.location_name,
        "time_local": ts_str,
        "temp_c": cw.temperature,
        "humidity": cw.humidity,
        "pressure_hpa": cw.pressure,
        "wind_speed": cw.wind_speed,
        "description": cw.description,
    }



def load_grid_cells() -> List[Dict[str, str]]:
    """
    Load ndvi_grid_cells.csv into a list of dicts:
        {'cell_id', 'row_label', 'col_label', 'mean_ndvi', 'class'}
    If the CSV does not exist, return [].
    """
    if not NDVI_GRID_CELLS_CSV.exists():
        return []

    cells: List[Dict[str, str]] = []
    with NDVI_GRID_CELLS_CSV.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cells.append(row)
    return cells


def generate_html(
    ndvi_stats: Dict[str, Any],
    weather_ctx: Dict[str, Any],
    grid_cells: List[Dict[str, str]],
) -> str:
    if NDVI_COLOR_PNG.exists():
        ndvi_img_tag = '<img src="ndvi/ndvi_color.png" alt="NDVI map" class="ndvi-img" />'
    else:
        ndvi_img_tag = "<p>No NDVI image found. Run the NDVI pipeline first.</p>"

    if NDVI_GRID_PNG.exists():
        ndvi_grid_tag = '<img src="ndvi/ndvi_grid_overlay.png" alt="NDVI grid overlay" class="ndvi-img" />'
    else:
        ndvi_grid_tag = "<p>No NDVI grid overlay found. Run the NDVI grid step.</p>"

    cells_link = "ndvi/ndvi_grid_cells.csv" if NDVI_GRID_CELLS_CSV.exists() else None
    cats_link = "ndvi/ndvi_grid_categories.csv" if NDVI_GRID_CATEGORIES_CSV.exists() else None

    csv_links_html_parts = []
    if cells_link:
        csv_links_html_parts.append(f'<a href="{cells_link}" download>Per-cell NDVI CSV</a>')
    if cats_link:
        csv_links_html_parts.append(f'<a href="{cats_link}" download>Categories CSV</a>')

    csv_links_html = " | ".join(csv_links_html_parts) if csv_links_html_parts else "<em>No NDVI CSVs found.</em>"

    # Build HTML rows for grid table
    grid_rows_html = ""
    for cell in grid_cells:
        cls = cell.get("class", "")
        mean_str = cell.get("mean_ndvi", "")
        cell_id = cell.get("cell_id", "")
        row_label = cell.get("row_label", "")
        col_label = cell.get("col_label", "")

        # CSS class for coloring
        tr_class = f"class-{cls}" if cls else ""
        grid_rows_html += f"""
        <tr class="{tr_class}">
          <td>{cell_id}</td>
          <td>{row_label}</td>
          <td>{col_label}</td>
          <td>{mean_str}</td>
          <td>{cls}</td>
        </tr>
        """

    if not grid_rows_html:
        grid_table_html = "<p>No grid data available (run NDVI grid step first).</p>"
    else:
        grid_table_html = f"""
        <div class="grid-table-wrapper">
          <table class="grid-table">
            <thead>
              <tr>
                <th>Cell ID</th>
                <th>Row</th>
                <th>Col</th>
                <th>Mean NDVI</th>
                <th>Class</th>
              </tr>
            </thead>
            <tbody>
              {grid_rows_html}
            </tbody>
          </table>
        </div>
        """

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>AgriVision Field Report</title>
<style>
    body {{
        font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        margin: 0;
        padding: 0;
        background-color: #f4f4f4;
        color: #222;
    }}
    header {{
        background-color: #114b5f;
        color: white;
        padding: 1.5rem 2rem;
    }}
    header h1 {{
        margin: 0 0 0.25rem 0;
        font-size: 1.6rem;
    }}
    header p {{
        margin: 0;
        opacity: 0.8;
    }}
    main {{
        max-width: 1100px;
        margin: 2rem auto;
        padding: 0 1rem 3rem;
    }}
    section {{
        background-color: #ffffff;
        border-radius: 8px;
        padding: 1.5rem;
        margin-bottom: 1.5rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    }}
    h2 {{
        margin-top: 0;
        font-size: 1.3rem;
        color: #114b5f;
    }}
    .ndvi-img {{
        max-width: 100%;
        height: auto;
        display: block;
        margin: 0 auto;
        border-radius: 6px;
        border: 1px solid #ddd;
    }}
    .stats-table {{
        width: 100%;
        border-collapse: collapse;
        margin-top: 0.5rem;
    }}
    .stats-table th,
    .stats-table td {{
        border: 1px solid #ddd;
        padding: 0.4rem 0.6rem;
        text-align: left;
        font-size: 0.9rem;
    }}
    .stats-table th {{
        background-color: #f0f4f5;
    }}
    .meta-note {{
        font-size: 0.85rem;
        color: #555;
        margin-top: 0.5rem;
    }}
    .csv-links {{
        margin-top: 0.6rem;
        font-size: 0.9rem;
    }}
    .csv-links a {{
        color: #114b5f;
        text-decoration: none;
        font-weight: 500;
    }}
    .csv-links a:hover {{
        text-decoration: underline;
    }}

    /* Grid table */
    .grid-table-wrapper {{
        max-height: 400px;
        overflow-y: auto;
        margin-top: 1rem;
        border: 1px solid #ddd;
        border-radius: 6px;
    }}
    .grid-table {{
        width: 100%;
        border-collapse: collapse;
        font-size: 0.85rem;
    }}
    .grid-table th,
    .grid-table td {{
        border: 1px solid #ddd;
        padding: 0.35rem 0.5rem;
        text-align: center;
    }}
    .grid-table thead th {{
        position: sticky;
        top: 0;
        background-color: #f2f6f7;
        z-index: 1;
    }}

    /* Row coloring by class */
    .class-poor {{ background-color: #ffe0e0; }}
    .class-medium {{ background-color: #fff9d9; }}
    .class-good {{ background-color: #e4ffe0; }}
    .class-no_data {{ background-color: #f0f0f0; color: #777; }}
</style>
</head>
<body>
<header>
  <h1>AgriVision Field Report</h1>
  <p>{weather_ctx.get("location_name", "Field location")} – generated {datetime.now().strftime("%Y-%m-%d %H:%M")}</p>
</header>

<main>

<section>
  <h2>Current Weather (OpenAgri WeatherService)</h2>
  <p><strong>Time:</strong> {weather_ctx.get("time_local", "N/A")}</p>
  <p><strong>Temperature:</strong> {weather_ctx.get("temp_c", "N/A")} °C</p>
  <p><strong>Humidity:</strong> {weather_ctx.get("humidity", "N/A")} %</p>
  <p><strong>Pressure:</strong> {weather_ctx.get("pressure_hpa", "N/A")} hPa</p>
  <p><strong>Wind speed:</strong> {weather_ctx.get("wind_speed", "N/A")} m/s</p>
  <p><strong>Conditions:</strong> {weather_ctx.get("description", "N/A")}</p>
  <p class="meta-note">
    Weather data provided by the OpenAgri WeatherService for the configured field location.
  </p>
</section>

<section>
  <h2>NDVI Overview</h2>
  {ndvi_img_tag}
  <table class="stats-table">
    <tr>
      <th>Statistic</th>
      <th>Value</th>
    </tr>
    <tr>
      <td>NDVI minimum</td>
      <td>{_fmt(ndvi_stats.get("min"))}</td>
    </tr>
    <tr>
      <td>NDVI maximum</td>
      <td>{_fmt(ndvi_stats.get("max"))}</td>
    </tr>
    <tr>
      <td>NDVI mean</td>
      <td>{_fmt(ndvi_stats.get("mean"))}</td>
    </tr>
  </table>
  <p class="meta-note">
    NDVI values range from -1 (no vegetation) to +1 (dense healthy vegetation).
  </p>
</section>

<section>
  <h2>NDVI Grid &amp; CSV Reports</h2>
  {ndvi_grid_tag}
  <div class="csv-links">
    {csv_links_html}
  </div>
  <p class="meta-note">
    The grid divides the field into {CONFIG["ndvi"]["grid_rows"]} × {CONFIG["ndvi"]["grid_cols"]} cells.
  </p>
</section>

<section>
  <h2>Per-cell NDVI Table</h2>
  <p class="meta-note">
    Each row corresponds to a grid cell (same IDs as in the overlay image), with its mean NDVI and class.
  </p>
  {grid_table_html}
</section>

</main>
</body>
</html>
"""
    return html


def run_report() -> None:
    ndvi_stats = read_ndvi_stats()
    weather_ctx = build_weather_context()
    grid_cells = load_grid_cells()

    REPORT_HTML.parent.mkdir(parents=True, exist_ok=True)
    html = generate_html(ndvi_stats, weather_ctx, grid_cells)
    REPORT_HTML.write_text(html, encoding="utf-8")

    print(f"[AgriVision] Report written to: {REPORT_HTML}")
    print("[AgriVision] Open it in a browser, for example:")
    print(f"  firefox {REPORT_HTML}")


if __name__ == "__main__":
    run_report()

