"""High-level report sections for methodology, grid metadata, and irrigation."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from agrivision.pipeline.report.assets import rel_to_report
from agrivision.pipeline.report.html import safe_html


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
