#!/usr/bin/env python3
"""
generate_report.py

Generate a static HTML report that combines:

- Latest NDVI map (from output/ndvi/ndvi_color.png)
- NDVI stats (min / max / mean)
- NDVI grid overlay + CSV links (per-cell + per-category)
- Weather summary from OpenAgri / OpenWeather
- THI (heat stress) information
- Spraying advisory (next hours)

Output:
    output/report_latest.html

Usage (from project root):

    source venv/bin/activate
    python3 scripts/generate_report.py
"""

from pathlib import Path
from datetime import datetime

import numpy as np
import rasterio

from openagri_farmer_report import (
    fetch_onecall,
    to_local_time,
    calculate_thi,
    classify_thi,
    classify_spray_window,
    beaufort_scale,
    wind_direction_from_deg,
)

BASE_DIR = Path(__file__).resolve().parent.parent

NDVI_TIF = BASE_DIR / "output" / "ndvi" / "ndvi.tif"
NDVI_PNG = BASE_DIR / "output" / "ndvi" / "ndvi_color.png"
REPORT_HTML = BASE_DIR / "output" / "report_latest.html"

NDVI_GRID_PNG = BASE_DIR / "output" / "ndvi" / "ndvi_grid_overlay.png"
NDVI_GRID_CELLS_CSV = BASE_DIR / "output" / "ndvi" / "ndvi_grid_cells.csv"
NDVI_GRID_CATEGORIES_CSV = BASE_DIR / "output" / "ndvi" / "ndvi_grid_categories.csv"


def read_ndvi_stats():
    """
    Read NDVI GeoTIFF and compute basic stats.

    Returns a dict with keys: available (bool), min, max, mean.
    """
    if not NDVI_TIF.exists():
        return {
            "available": False,
            "min": None,
            "max": None,
            "mean": None,
        }

    with rasterio.open(NDVI_TIF) as src:
        ndvi = src.read(1)

    ndvi = ndvi.astype("float32")
    mask = np.isfinite(ndvi)
    if not mask.any():
        return {
            "available": False,
            "min": None,
            "max": None,
            "mean": None,
        }

    vals = ndvi[mask]
    return {
        "available": True,
        "min": float(vals.min()),
        "max": float(vals.max()),
        "mean": float(vals.mean()),
    }


def build_weather_context(hours_ahead: int = 8) -> dict:
    """
    Fetch weather from OpenAgri / OpenWeather and build a small context dict.
    """
    data = fetch_onecall()
    current = data.get("current", {})
    hourly = data.get("hourly", [])
    tz_offset = data.get("timezone_offset", 0)

    # ---- current ----
    temp = current.get("temp")
    feels_like = current.get("feels_like")
    rh = current.get("humidity")
    pressure = current.get("pressure")
    clouds = current.get("clouds")
    vis = current.get("visibility")
    uvi = current.get("uvi")
    wind_speed = current.get("wind_speed")
    wind_deg = current.get("wind_deg")
    weather_list = current.get("weather", [])
    description = weather_list[0]["description"] if weather_list else "N/A"
    dt = current.get("dt")

    thi = calculate_thi(temp, rh)
    thi_class = classify_thi(thi)

    current_ctx = {
        "time_local": to_local_time(dt, tz_offset) if dt is not None else "N/A",
        "temp_c": temp,
        "feels_like_c": feels_like,
        "humidity": rh,
        "pressure_hpa": pressure,
        "clouds_pct": clouds,
        "visibility_m": vis,
        "uv_index": uvi,
        "wind_speed_ms": wind_speed,
        "wind_beaufort": beaufort_scale(wind_speed),
        "wind_deg": wind_deg,
        "wind_dir": wind_direction_from_deg(wind_deg),
        "conditions": description,
        "thi": thi,
        "thi_class": thi_class,
    }

    # ---- spray advisory next N hours ----
    spray_rows = []
    for h in hourly[:hours_ahead]:
        hdt = h.get("dt")
        time_str = to_local_time(hdt, tz_offset) if hdt else "?"
        wind = h.get("wind_speed", 0.0)
        pop = h.get("pop", 0.0)
        rain_amount = 0.0
        if "rain" in h:
            rain_amount = h["rain"].get("1h", 0.0)
        cond = classify_spray_window(h)
        desc = h.get("weather", [{}])[0].get("description", "N/A")

        spray_rows.append({
            "time_local": time_str,
            "advisory": cond,
            "wind_speed_ms": wind,
            "rain_mm": rain_amount,
            "pop_pct": int(pop * 100),
            "description": desc,
        })

    return {
        "current": current_ctx,
        "spray_windows": spray_rows,
    }


def generate_html(ndvi_stats: dict, weather_ctx: dict) -> str:
    """
    Build the HTML string for the report.
    """
    now_str = datetime.now().strftime("%d/%m/%Y %H:%M")

    # NDVI image
    if NDVI_PNG.exists():
        ndvi_img_tag = '<img src="ndvi/ndvi_color.png" alt="NDVI map" class="ndvi-img" />'
    else:
        ndvi_img_tag = "<p>No NDVI image found. Run the NDVI pipeline first.</p>"

    # NDVI grid overlay
    if NDVI_GRID_PNG.exists():
        ndvi_grid_tag = '<img src="ndvi/ndvi_grid_overlay.png" alt="NDVI grid overlay" class="ndvi-img" />'
    else:
        ndvi_grid_tag = "<p>No NDVI grid overlay found. Run ndvi_grid_report.py.</p>"

    # CSV links
    cells_link = "ndvi/ndvi_grid_cells.csv" if NDVI_GRID_CELLS_CSV.exists() else None
    cats_link = "ndvi/ndvi_grid_categories.csv" if NDVI_GRID_CATEGORIES_CSV.exists() else None

    csv_links_html_parts = []
    if cells_link:
        csv_links_html_parts.append(f'<a href="{cells_link}">Download per-cell NDVI (CSV)</a>')
    if cats_link:
        csv_links_html_parts.append(f'<a href="{cats_link}">Download category table (CSV)</a>')

    csv_links_html = "<br/>".join(csv_links_html_parts) if csv_links_html_parts else "<em>No grid CSV files found.</em>"

    cur = weather_ctx["current"]

    # Safe string helpers
    def fmt(val, suffix=""):
        return "N/A" if val is None else f"{val}{suffix}"

    # Spray table rows
    spray_rows_html = ""
    for row in weather_ctx["spray_windows"]:
        spray_rows_html += f"""
        <tr class="spray-{row['advisory'].lower()}">
            <td>{row['time_local']}</td>
            <td>{row['advisory']}</td>
            <td>{row['wind_speed_ms']:.1f}</td>
            <td>{row['rain_mm']:.1f}</td>
            <td>{row['pop_pct']}%</td>
            <td>{row['description']}</td>
        </tr>
        """

    if ndvi_stats["available"]:
        ndvi_stats_html = f"""
            <p><strong>NDVI min:</strong> {ndvi_stats['min']:.3f}</p>
            <p><strong>NDVI max:</strong> {ndvi_stats['max']:.3f}</p>
            <p><strong>NDVI mean:</strong> {ndvi_stats['mean']:.3f}</p>
        """
    else:
        ndvi_stats_html = "<p>No NDVI statistics available.</p>"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<title>AgriVision Farm Report</title>
<style>
    body {{
        font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        background: #f5f5f5;
        margin: 0;
        padding: 0;
        color: #222;
    }}
    .page {{
        max-width: 1100px;
        margin: 0 auto;
        padding: 20px 20px 40px;
    }}
    h1, h2, h3 {{
        margin-top: 0;
    }}
    .header {{
        display: flex;
        justify-content: space-between;
        align-items: baseline;
        border-bottom: 1px solid #ddd;
        padding-bottom: 8px;
        margin-bottom: 16px;
    }}
    .header-title {{
        font-size: 1.8rem;
        font-weight: 600;
    }}
    .header-meta {{
        font-size: 0.9rem;
        color: #666;
    }}
    .grid {{
        display: grid;
        grid-template-columns: minmax(0, 2fr) minmax(0, 1.4fr);
        gap: 20px;
        align-items: flex-start;
    }}
    .card {{
        background: #fff;
        border-radius: 12px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        padding: 16px 18px;
        margin-bottom: 20px;
    }}
    .card h2 {{
        font-size: 1.2rem;
        margin-bottom: 8px;
    }}
    .ndvi-img {{
        width: 100%;
        height: auto;
        border-radius: 10px;
        border: 1px solid #ddd;
    }}
    .kv {{
        display: flex;
        justify-content: space-between;
        margin-bottom: 4px;
        font-size: 0.95rem;
    }}
    .kv-label {{
        color: #555;
    }}
    .kv-value {{
        font-weight: 600;
    }}
    table {{
        width: 100%;
        border-collapse: collapse;
        font-size: 0.9rem;
    }}
    th, td {{
        border: 1px solid #ddd;
        padding: 6px 8px;
        text-align: left;
    }}
    th {{
        background: #f0f0f0;
    }}
    tr.spray-optimal {{
        background: #e6f4ea;
    }}
    tr.spray-marginal {{
        background: #fff7e0;
    }}
    tr.spray-unsuitable {{
        background: #fde2e1;
    }}
    .footnote {{
        font-size: 0.8rem;
        color: #777;
        margin-top: 8px;
    }}
</style>
</head>
<body>
<div class="page">
    <div class="header">
        <div class="header-title">AgriVision Field Report</div>
        <div class="header-meta">
            Generated: {now_str}<br/>
            Location: Rethymno, Crete (OpenAgri weather service)
        </div>
    </div>

    <div class="grid">
        <div>
            <div class="card">
                <h2>NDVI – Crop Health Map</h2>
                {ndvi_img_tag}
                <div style="margin-top: 10px;">
                    {ndvi_stats_html}
                </div>
                <p class="footnote">
                    NDVI &approx; (NIR - RED) / (NIR + RED). Higher values usually indicate healthier vegetation.
                </p>
            </div>

            <div class="card">
                <h2>NDVI Grid &amp; Zones</h2>
                {ndvi_grid_tag}
                <div style="margin-top: 10px;">
                    <p>
                        Each cell (A1, A2, ...) represents the average NDVI in that area.
                        Colors indicate:
                        <span style="color:red;font-weight:bold;"> poor</span>,
                        <span style="color:gold;font-weight:bold;"> medium</span>,
                        <span style="color:limegreen;font-weight:bold;"> good</span>,
                        <span style="color:gray;font-weight:bold;"> no data</span>.
                    </p>
                    <p>
                        {csv_links_html}
                    </p>
                </div>
                <p class="footnote">
                    Open the CSV files in Excel or LibreOffice to see lists of cells by category,
                    or to sort/filter by NDVI value.
                </p>
            </div>
        </div>

        <div>
            <div class="card">
                <h2>Current Weather</h2>
                <div class="kv">
                    <div class="kv-label">Time (local)</div>
                    <div class="kv-value">{cur['time_local']}</div>
                </div>
                <div class="kv">
                    <div class="kv-label">Temperature</div>
                    <div class="kv-value">{fmt(cur['temp_c'], ' °C')} (feels {fmt(cur['feels_like_c'], ' °C')})</div>
                </div>
                <div class="kv">
                    <div class="kv-label">Humidity</div>
                    <div class="kv-value">{fmt(cur['humidity'], ' %')}</div>
                </div>
                <div class="kv">
                    <div class="kv-label">Pressure</div>
                    <div class="kv-value">{fmt(cur['pressure_hpa'], ' hPa')}</div>
                </div>
                <div class="kv">
                    <div class="kv-label">Cloud cover</div>
                    <div class="kv-value">{fmt(cur['clouds_pct'], ' %')}</div>
                </div>
                <div class="kv">
                    <div class="kv-label">Visibility</div>
                    <div class="kv-value">{fmt(cur['visibility_m'], ' m')}</div>
                </div>
                <div class="kv">
                    <div class="kv-label">UV index</div>
                    <div class="kv-value">{fmt(cur['uv_index'])}</div>
                </div>
                <div class="kv">
                    <div class="kv-label">Wind</div>
                    <div class="kv-value">
                        {fmt(cur['wind_speed_ms'], ' m/s')}
                        ({cur['wind_beaufort']}) {cur['wind_dir']} ({fmt(cur['wind_deg'], '°')})
                    </div>
                </div>
                <div class="kv">
                    <div class="kv-label">Conditions</div>
                    <div class="kv-value">{cur['conditions']}</div>
                </div>
            </div>

            <div class="card">
                <h2>Heat Stress (THI)</h2>
                <p>
                    THI: <strong>{cur['thi']:.1f}</strong>
                    &nbsp;&rarr;&nbsp;
                    <strong>{cur['thi_class']}</strong>
                </p>
                <p class="footnote">
                    Higher THI indicates increased heat stress risk for crops and workers.
                </p>
            </div>
        </div>
    </div>

    <div class="card">
        <h2>Spraying Advisory (Next Hours)</h2>
        <table>
            <thead>
                <tr>
                    <th>Time (local)</th>
                    <th>Advisory</th>
                    <th>Wind (m/s)</th>
                    <th>Rain (mm)</th>
                    <th>Rain chance</th>
                    <th>Conditions</th>
                </tr>
            </thead>
            <tbody>
                {spray_rows_html}
            </tbody>
        </table>
        <p class="footnote">
            OPTIMAL: low wind, low rain chance. MARGINAL: borderline conditions. UNSUITABLE: avoid spraying.
        </p>
    </div>

</div>
</body>
</html>
"""
    return html


def main():
    print(f"[AgriVision] Generating HTML report at: {REPORT_HTML}")

    ndvi_stats = read_ndvi_stats()
    print(f"[AgriVision] NDVI stats: {ndvi_stats}")

    try:
        weather_ctx = build_weather_context(hours_ahead=8)
    except Exception as e:
        print(f"[AgriVision] ERROR: Could not fetch weather data: {e}")
        # Minimal fallback
        weather_ctx = {
            "current": {
                "time_local": "N/A",
                "temp_c": None,
                "feels_like_c": None,
                "humidity": None,
                "pressure_hpa": None,
                "clouds_pct": None,
                "visibility_m": None,
                "uv_index": None,
                "wind_speed_ms": None,
                "wind_beaufort": "unknown",
                "wind_deg": None,
                "wind_dir": "unknown",
                "conditions": "No weather data",
                "thi": 0.0,
                "thi_class": "No data",
            },
            "spray_windows": [],
        }

    html = generate_html(ndvi_stats, weather_ctx)

    REPORT_HTML.parent.mkdir(parents=True, exist_ok=True)
    REPORT_HTML.write_text(html, encoding="utf-8")

    print(f"[AgriVision] Report written to: {REPORT_HTML}")
    print("[AgriVision] You can open it in a browser, e.g.:")
    print(f"  firefox {REPORT_HTML}")


if __name__ == "__main__":
    main()

