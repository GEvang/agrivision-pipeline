"""High-level report sections for weather, methodology, grid metadata, and irrigation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from agrivision.pipeline.report.assets import rel_to_report
from agrivision.pipeline.report.html import safe_html


def _render_json_preview(title: str, payload: Any) -> str:
    if not payload:
        return f"<p><em>{safe_html(title)} not available for this run.</em></p>"
    preview = json.dumps(payload, indent=2, ensure_ascii=False)
    if len(preview) > 2500:
        preview = preview[:2500] + "\n..."
    return (
        f"<h4>{safe_html(title)}</h4>"
        "<pre style='white-space: pre-wrap; max-height: 260px; overflow:auto; border:1px solid #ddd; padding:10px;'>"
        f"{safe_html(preview)}</pre>"
    )


def _render_artifact_link_row(label: str, artifact_path: str, output_dir: Path) -> str:
    if not artifact_path:
        return f"<tr><th align='left'>{safe_html(label)}</th><td><em>Not available</em></td></tr>"
    try:
        path = Path(artifact_path)
        if path.exists():
            href = rel_to_report(path, output_dir)
            link_html = f'<a href="{safe_html(href)}">{safe_html(href)}</a>'
        else:
            link_html = "<em>Not found</em>"
    except Exception:
        link_html = "<em>Not available</em>"
    return f"<tr><th align='left'>{safe_html(label)}</th><td>{link_html}</td></tr>"


def render_weather_section(
    weather_summary: Optional[Dict[str, Any]],
    output_dir: Path,
) -> str:
    if not weather_summary:
        return (
            "<h2>OpenAgri Weather Service</h2>"
            "<p><em>No weather integration data provided for this run.</em></p>"
        )

    enabled = bool(weather_summary.get("enabled", True))
    location_name = weather_summary.get("location_name", "Unknown location")
    current = weather_summary.get("current_weather", {}) or {}
    forecast_points = weather_summary.get("forecast5_points", []) or []
    thi = weather_summary.get("thi", {}) or {}
    thi_jsonld = weather_summary.get("thi_jsonld", {}) or {}
    forecast5_jsonld = weather_summary.get("forecast5_jsonld", {}) or {}
    uav = weather_summary.get("uav_flight_forecast", {}) or {}
    spray = weather_summary.get("spray_forecast", {}) or {}
    spray_jsonld = weather_summary.get("spray_forecast_jsonld", {}) or {}
    historical_daily = weather_summary.get("historical_daily", {}) or {}
    historical_hourly = weather_summary.get("historical_hourly", {}) or {}
    notes = weather_summary.get("notes", []) or []

    status_label = "OK" if enabled else "Unavailable"
    status_color = "#2a5d34" if enabled else "#a13a3a"

    current_time = current.get("timestamp", "N/A")
    current_temp = current.get("temperature", "N/A")
    current_humidity = current.get("humidity", "N/A")
    current_wind = current.get("wind_speed", "N/A")
    current_pressure = current.get("pressure", "N/A")
    current_desc = current.get("description", "N/A")

    thi_data = thi.get("data", thi) if isinstance(thi, dict) else thi
    uav_data = uav.get("data", uav) if isinstance(uav, dict) else uav
    spray_data = spray.get("data", spray) if isinstance(spray, dict) else spray
    hist_daily_data = historical_daily.get("data", historical_daily) if isinstance(historical_daily, dict) else historical_daily
    hist_hourly_data = historical_hourly.get("data", historical_hourly) if isinstance(historical_hourly, dict) else historical_hourly

    forecast_rows = []
    for item in forecast_points[:8]:
        forecast_rows.append(
            "<tr>"
            f"<td>{safe_html(item.get('timestamp', 'N/A'))}</td>"
            f"<td>{safe_html(item.get('measurement_type', item.get('data_type', 'N/A')))}</td>"
            f"<td>{safe_html(item.get('value', 'N/A'))}</td>"
            f"<td>{safe_html(item.get('source', 'N/A'))}</td>"
            "</tr>"
        )
    if not forecast_rows:
        forecast_rows.append("<tr><td colspan='4'><em>No forecast points available.</em></td></tr>")

    notes_html = ""
    if isinstance(notes, list) and notes:
        notes_html = "<ul>" + "".join(f"<li>{safe_html(note)}</li>" for note in notes) + "</ul>"

    artifact_rows = "".join(
        [
            _render_artifact_link_row("Current weather JSON", weather_summary.get("current_weather_artifact", ""), output_dir),
            _render_artifact_link_row("Forecast JSON", weather_summary.get("forecast_json_artifact", ""), output_dir),
            _render_artifact_link_row("Forecast JSON-LD", weather_summary.get("forecast_jsonld_artifact", ""), output_dir),
            _render_artifact_link_row("THI JSON", weather_summary.get("thi_artifact", ""), output_dir),
            _render_artifact_link_row("THI JSON-LD", weather_summary.get("thi_jsonld_artifact", ""), output_dir),
            _render_artifact_link_row("UAV flight forecast JSON", weather_summary.get("uav_artifact", ""), output_dir),
            _render_artifact_link_row("Spray forecast JSON", weather_summary.get("spray_artifact", ""), output_dir),
            _render_artifact_link_row("Spray forecast JSON-LD", weather_summary.get("spray_jsonld_artifact", ""), output_dir),
            _render_artifact_link_row("Historical daily JSON", weather_summary.get("historical_daily_artifact", ""), output_dir),
            _render_artifact_link_row("Historical hourly JSON", weather_summary.get("historical_hourly_artifact", ""), output_dir),
        ]
    )

    return f"""
<h2>OpenAgri Weather Service</h2>
<p>
  This run includes current weather conditions, 5-day forecasts, JSON-LD/OCSM outputs,
  agricultural indicators, UAV flight forecasts, spray condition forecasts, and historical weather values.
</p>

<table border="1" cellpadding="6" cellspacing="0">
  <tr><th align="left">Status</th><td><span style="color:{status_color}; font-weight:bold;">{safe_html(status_label)}</span></td></tr>
  <tr><th align="left">Location</th><td>{safe_html(location_name)}</td></tr>
  <tr><th align="left">Report history range</th><td>{safe_html(weather_summary.get('history_start_date', 'N/A'))} → {safe_html(weather_summary.get('history_end_date', 'N/A'))}</td></tr>
  <tr><th align="left">UAV model</th><td>{safe_html(weather_summary.get('uav_model', 'N/A'))}</td></tr>
</table>

<h3>Current Weather Conditions</h3>
<table border="1" cellpadding="6" cellspacing="0">
  <tr><th align="left">Observed at</th><td>{safe_html(current_time)}</td></tr>
  <tr><th align="left">Temperature</th><td>{safe_html(current_temp)} °C</td></tr>
  <tr><th align="left">Humidity</th><td>{safe_html(current_humidity)} %</td></tr>
  <tr><th align="left">Wind speed</th><td>{safe_html(current_wind)} m/s</td></tr>
  <tr><th align="left">Pressure</th><td>{safe_html(current_pressure)} hPa</td></tr>
  <tr><th align="left">Sky conditions</th><td>{safe_html(current_desc)}</td></tr>
</table>

<h3>5-Day Forecast Preview</h3>
<table border="1" cellpadding="6" cellspacing="0">
  <thead>
    <tr>
      <th>Timestamp</th>
      <th>Measure</th>
      <th>Value</th>
      <th>Source</th>
    </tr>
  </thead>
  <tbody>
    {''.join(forecast_rows)}
  </tbody>
</table>

<h3>Agricultural Indicators (THI)</h3>
<div class="subtle-card">
  {_render_json_preview('THI JSON', thi_data)}
  {_render_json_preview('THI JSON-LD / OCSM', thi_jsonld)}
</div>

<h3>UAV Flight Forecast</h3>
<div class="subtle-card">
  {_render_json_preview('UAV flight forecast', uav_data)}
</div>

<h3>Spray Condition Forecast</h3>
<div class="subtle-card">
  {_render_json_preview('Spray forecast JSON', spray_data)}
  {_render_json_preview('Spray forecast JSON-LD / OCSM', spray_jsonld)}
</div>

<h3>Historical Weather API</h3>
<div class="subtle-card">
  {_render_json_preview('Historical daily values', hist_daily_data)}
  {_render_json_preview('Historical hourly values', hist_hourly_data)}
</div>

<h3>Weather Artifacts</h3>
<table border="1" cellpadding="6" cellspacing="0">
  {artifact_rows}
</table>

<h3>Forecast JSON-LD / OCSM Preview</h3>
{_render_json_preview('Forecast JSON-LD / OCSM', forecast5_jsonld)}

{notes_html}
""".strip()


def render_methodology_section(meta: dict) -> str:
    if not meta:
        return (
            "<h2>Vegetation Index Methodology</h2>"
            "<p><em>No metadata available for this run (metadata.json missing or unreadable).</em></p>"
        )

    index = meta.get("index", {}) or {}
    thresholds = meta.get("classification_thresholds", {}) or {}
    source = meta.get("source", {}) or {}
    band_map = index.get("band_mapping", {}) or {}

    band_map_str = "N/A"
    if isinstance(band_map, dict) and band_map:
        band_map_str = ", ".join(f"{safe_html(k)} = {safe_html(v)}" for k, v in band_map.items())

    notes_html = ""
    notes = meta.get("notes", [])
    if isinstance(notes, list) and notes:
        notes_html = "<ul>" + "".join(f"<li>{safe_html(n)}</li>" for n in notes) + "</ul>"

    return f"""
<h2>Vegetation Index Methodology</h2>
<table border="1" cellpadding="6" cellspacing="0">
  <tr><th align="left">Index type</th><td>{safe_html(index.get("index_name", "Unknown"))}</td></tr>
  <tr><th align="left">Formula</th><td><code>{safe_html(index.get("formula", "N/A"))}</code></td></tr>
  <tr><th align="left">Source dataset</th><td>{safe_html(source.get("dataset", "Unknown"))}</td></tr>
  <tr><th align="left">Band mapping</th><td>{band_map_str}</td></tr>
  <tr><th align="left">Configured poor threshold (max)</th><td>{safe_html(thresholds.get("poor_max", "N/A"))}</td></tr>
  <tr><th align="left">Configured medium threshold (max)</th><td>{safe_html(thresholds.get("medium_max", "N/A"))}</td></tr>
  <tr><th align="left">Generated at (UTC)</th><td>{safe_html(meta.get("generated_at_utc", "N/A"))}</td></tr>
</table>
{notes_html}
""".strip()


def render_grid_metadata_section(grid_meta: dict) -> str:
    if not grid_meta:
        return (
            "<h3>Grid Classification Details</h3>"
            "<p><em>No grid metadata available (grid_metadata.json missing or unreadable).</em></p>"
        )

    mode = grid_meta.get("classification_mode", "Unknown")
    thresholds_used = grid_meta.get("thresholds_used", {}) or {}
    poor_used = thresholds_used.get("poor_max", "N/A")
    medium_used = thresholds_used.get("medium_max", "N/A")
    generated_at = grid_meta.get("generated_at_utc", "N/A")
    index_name = grid_meta.get("index_name", "Vegetation Index")

    mode_expl = "Unknown."
    if mode == "fixed":
        mode_expl = "Fixed thresholds from configuration were applied."
    elif mode == "percentile_fallback":
        mode_expl = (
            "Percentile-based thresholds were applied because fixed thresholds produced "
            "insufficient class separation."
        )

    return f"""
<h3>Grid Classification Details</h3>
<table border="1" cellpadding="6" cellspacing="0">
  <tr><th align="left">Index</th><td>{safe_html(index_name)}</td></tr>
  <tr><th align="left">Classification mode</th><td>{safe_html(mode)}</td></tr>
  <tr><th align="left">Mode explanation</th><td>{safe_html(mode_expl)}</td></tr>
  <tr><th align="left">Poor threshold used (max)</th><td>{safe_html(poor_used)}</td></tr>
  <tr><th align="left">Medium threshold used (max)</th><td>{safe_html(medium_used)}</td></tr>
  <tr><th align="left">Grid metadata generated at (UTC)</th><td>{safe_html(generated_at)}</td></tr>
</table>
""".strip()


def render_irrigation_section(
    irrigation_summary: Optional[Dict[str, Any]],
    output_dir: Path,
) -> str:
    if not irrigation_summary:
        return (
            "<h2>Irrigation Service Integration</h2>"
            "<p><em>No irrigation integration data provided for this run.</em></p>"
        )

    enabled = bool(irrigation_summary.get("enabled", True))
    authenticated = bool(irrigation_summary.get("authenticated", False))
    base_url = irrigation_summary.get("base_url", "")
    email = irrigation_summary.get("email", "")
    parcel_count = irrigation_summary.get("parcel_count", "unknown")
    created_default = bool(irrigation_summary.get("created_default_parcel", False))
    notes = irrigation_summary.get("notes", [])

    eto = irrigation_summary.get("eto", {}) or {}
    eto_method = eto.get("method", "get_calculations")
    eto_ok = bool(eto.get("ok", False))
    eto_status = eto.get("http_status", None)
    eto_location_id = eto.get("location_id", "")
    eto_from = eto.get("from_date", "")
    eto_to = eto.get("to_date", "")
    eto_count = eto.get("count", None)
    eto_preview = eto.get("preview", "")
    eto_artifact_path = eto.get("artifact_path", "")

    status_label = "OK" if authenticated else "Not authenticated / unavailable"
    status_color = "#2a5d34" if authenticated else "#a13a3a"

    notes_html = ""
    if isinstance(notes, list) and notes:
        notes_html = "<ul>" + "".join(f"<li>{safe_html(n)}</li>" for n in notes) + "</ul>"

    eto_label = "OK" if eto_ok else "Failed"
    eto_color = "#2a5d34" if eto_ok else "#a13a3a"

    eto_link_html = ""
    try:
        eto_path = Path(eto_artifact_path)
        if eto_path.exists():
            href = rel_to_report(eto_path, output_dir)
            eto_link_html = f'<a href="{safe_html(href)}">{safe_html(href)}</a>'
        else:
            eto_link_html = "<em>Not found</em>"
    except Exception:
        eto_link_html = "<em>Not available</em>"

    if eto_ok and eto_count == 0:
        eto_count_msg = (
            "0 values (no calculations returned yet — expected if meteo ingestion hasn’t "
            "populated the DB for this range)"
        )
    elif eto_count is None:
        eto_count_msg = "Unknown (response schema not recognized)"
    else:
        eto_count_msg = str(eto_count)

    eto_preview_html = ""
    if eto_preview:
        eto_preview_html = (
            "<pre style='white-space: pre-wrap; max-height: 260px; overflow:auto; "
            f"border:1px solid #ddd; padding:10px;'>{safe_html(eto_preview)}</pre>"
        )

    return f"""
<h2>Irrigation Service Integration</h2>
<p>
  This run includes an integration check against the OpenAgri Irrigation Management Service:
  authentication, parcel availability, and ETo retrieval using the official <code>{safe_html(eto_method)}</code> workflow.
</p>

<table border="1" cellpadding="6" cellspacing="0">
  <tr><th align="left">Enabled</th><td>{safe_html(enabled)}</td></tr>
  <tr><th align="left">Service URL</th><td>{safe_html(base_url)}</td></tr>
  <tr><th align="left">Status</th><td><span style="color:{status_color}; font-weight:bold;">{safe_html(status_label)}</span></td></tr>
  <tr><th align="left">Authenticated as</th><td>{safe_html(email)}</td></tr>
  <tr><th align="left">Parcels visible to user</th><td>{safe_html(parcel_count)}</td></tr>
  <tr><th align="left">Created default parcel this run</th><td>{safe_html(created_default)}</td></tr>
</table>

<h3>ETo (FAO-56 Penman–Monteith) — Official get-calculations workflow</h3>
<table border="1" cellpadding="6" cellspacing="0">
  <tr><th align="left">Request status</th><td><span style="color:{eto_color}; font-weight:bold;">{safe_html(eto_label)}</span> (HTTP {safe_html(eto_status)})</td></tr>
  <tr><th align="left">Location ID</th><td>{safe_html(eto_location_id)}</td></tr>
  <tr><th align="left">Date range</th><td>{safe_html(eto_from)} → {safe_html(eto_to)}</td></tr>
  <tr><th align="left">Returned values</th><td>{safe_html(eto_count_msg)}</td></tr>
  <tr><th align="left">Raw response artifact</th><td>{eto_link_html}</td></tr>
</table>

{eto_preview_html}

{notes_html}
""".strip()
