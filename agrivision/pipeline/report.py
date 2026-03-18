#!/usr/bin/env python3
"""
agrivision.pipeline.report

Generate the final HTML report for AgriVision.

Includes:
- Vegetation index methodology + artifacts
- Grid analysis table
- Irrigation integration summary:
  - service status + auth
  - parcel count
  - ETo get-calculations request summary + count + preview + link to eto.json
"""

from __future__ import annotations

import csv
import html
import json
from datetime import datetime
from json import JSONDecodeError
from pathlib import Path
from typing import Any, Dict, List, Optional

from agrivision.utils.settings import get_project_root, load_config

CONFIG = load_config()
PROJECT_ROOT = get_project_root()

OUTPUT_DIR = PROJECT_ROOT / CONFIG["paths"]["output_root"]
REPORT_PATH = OUTPUT_DIR / "report_latest.html"

NDVI_DIR = PROJECT_ROOT / CONFIG["paths"]["ndvi_output"]

NDVI_META_PATH = NDVI_DIR / "metadata.json"
GRID_META_PATH = NDVI_DIR / "grid_metadata.json"

NDVI_TIF = NDVI_DIR / "ndvi.tif"
NDVI_COLOR_PNG = NDVI_DIR / "ndvi_color.png"
GRID_OVERLAY_PNG = NDVI_DIR / "ndvi_grid_overlay.png"
GRID_CELLS_CSV = NDVI_DIR / "ndvi_grid_cells.csv"
GRID_CATEGORIES_CSV = NDVI_DIR / "ndvi_grid_categories.csv"


def _rel_to_report(abs_path: Path) -> str:
    try:
        rel = abs_path.relative_to(OUTPUT_DIR)
        return rel.as_posix()
    except ValueError:
        return abs_path.name


def _safe(s: object) -> str:
    if s is None:
        return ""
    return html.escape(str(s), quote=True)


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, JSONDecodeError):
        return {}


def _get_index_title(ndvi_meta: dict, grid_meta: dict) -> str:
    idx = (ndvi_meta.get("index", {}) or {}).get("index_name")
    if idx:
        return str(idx)
    idx2 = grid_meta.get("index_name")
    if idx2:
        return str(idx2)
    return "Vegetation Index"


def _render_methodology_section(meta: dict) -> str:
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
        band_map_str = ", ".join(f"{_safe(k)} = {_safe(v)}" for k, v in band_map.items())

    notes_html = ""
    notes = meta.get("notes", [])
    if isinstance(notes, list) and notes:
        notes_html = "<ul>" + "".join(f"<li>{_safe(n)}</li>" for n in notes) + "</ul>"

    return f"""
<h2>Vegetation Index Methodology</h2>
<table border="1" cellpadding="6" cellspacing="0">
  <tr><th align="left">Index type</th><td>{_safe(index.get("index_name", "Unknown"))}</td></tr>
  <tr><th align="left">Formula</th><td><code>{_safe(index.get("formula", "N/A"))}</code></td></tr>
  <tr><th align="left">Source dataset</th><td>{_safe(source.get("dataset", "Unknown"))}</td></tr>
  <tr><th align="left">Band mapping</th><td>{band_map_str}</td></tr>
  <tr><th align="left">Configured poor threshold (max)</th><td>{_safe(thresholds.get("poor_max", "N/A"))}</td></tr>
  <tr><th align="left">Configured medium threshold (max)</th><td>{_safe(thresholds.get("medium_max", "N/A"))}</td></tr>
  <tr><th align="left">Generated at (UTC)</th><td>{_safe(meta.get("generated_at_utc", "N/A"))}</td></tr>
</table>
{notes_html}
""".strip()


def _render_grid_metadata_section(grid_meta: dict) -> str:
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
        mode_expl = "Percentile-based thresholds were applied because fixed thresholds produced insufficient class separation."

    return f"""
<h3>Grid Classification Details</h3>
<table border="1" cellpadding="6" cellspacing="0">
  <tr><th align="left">Index</th><td>{_safe(index_name)}</td></tr>
  <tr><th align="left">Classification mode</th><td>{_safe(mode)}</td></tr>
  <tr><th align="left">Mode explanation</th><td>{_safe(mode_expl)}</td></tr>
  <tr><th align="left">Poor threshold used (max)</th><td>{_safe(poor_used)}</td></tr>
  <tr><th align="left">Medium threshold used (max)</th><td>{_safe(medium_used)}</td></tr>
  <tr><th align="left">Grid metadata generated at (UTC)</th><td>{_safe(generated_at)}</td></tr>
</table>
""".strip()


def _render_artifact_link(label: str, path: Path) -> str:
    if path.exists():
        href = _rel_to_report(path)
        return f'<li><strong>{_safe(label)}:</strong> <a href="{_safe(href)}">{_safe(href)}</a></li>'
    return f"<li><strong>{_safe(label)}:</strong> <em>Not found</em></li>"


def _render_image_if_exists(title: str, path: Path) -> str:
    if not path.exists():
        return f"<p><em>{_safe(title)} not found.</em></p>"
    src = _rel_to_report(path)
    return f"""
<h3>{_safe(title)}</h3>
<img src="{_safe(src)}" alt="{_safe(title)}" style="max-width: 100%; height: auto; border: 1px solid #ddd;" />
""".strip()


def _load_grid_cells() -> List[Dict[str, str]]:
    if not GRID_CELLS_CSV.exists():
        return []
    rows: List[Dict[str, str]] = []
    with GRID_CELLS_CSV.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)
    return rows


def _render_grid_table(index_title: str, rows: List[Dict[str, str]]) -> str:
    if not rows:
        return "<p><em>No grid cell CSV available.</em></p>"

    body = []
    for r in rows:
        mean_val = r.get("mean_index")
        if mean_val in (None, ""):
            mean_val = r.get("mean_ndvi", "")

        cls = r.get("class", "")
        row_class = f"class-{cls}" if cls else ""

        body.append(
            f"""
<tr class="{_safe(row_class)}">
  <td>{_safe(r.get("cell_id", ""))}</td>
  <td>{_safe(r.get("row_label", ""))}</td>
  <td>{_safe(r.get("col_label", ""))}</td>
  <td>{_safe(mean_val)}</td>
  <td>{_safe(cls)}</td>
</tr>
""".strip()
        )
        
    body_html = "\n".join(body)
    return f"""
<div style="max-height: 420px; overflow-y: auto; border: 1px solid #ddd; padding: 0; margin-top: 10px;">
  <table style="width: 100%; border-collapse: collapse;" border="1" cellpadding="6" cellspacing="0">
    <thead style="position: sticky; top: 0; background: #f0f0f0;">
      <tr>
        <th align="left">Cell ID</th>
        <th align="left">Row</th>
        <th align="left">Col</th>
        <th align="left">Mean { _safe(index_title) }</th>
        <th align="left">Class</th>
      </tr>
    </thead>
    <tbody>
      {body_html}
    </tbody>
  </table>
</div>

<style>
  .class-poor {{ background-color: #ffe0e0; }}
  .class-medium {{ background-color: #fff9d9; }}
  .class-good {{ background-color: #e4ffe0; }}
  .class-no_data {{ background-color: #f0f0f0; color: #777; }}
</style>
""".strip()


def _render_irrigation_section(irrigation_summary: Optional[Dict[str, Any]]) -> str:
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
        notes_html = "<ul>" + "".join(f"<li>{_safe(n)}</li>" for n in notes) + "</ul>"

    eto_label = "OK" if eto_ok else "Failed"
    eto_color = "#2a5d34" if eto_ok else "#a13a3a"

    # artifact link (eto.json)
    eto_link_html = ""
    try:
        eto_path = Path(eto_artifact_path)
        if eto_path.exists():
            href = _rel_to_report(eto_path)
            eto_link_html = f'<a href="{_safe(href)}">{_safe(href)}</a>'
        else:
            eto_link_html = "<em>Not found</em>"
    except Exception:
        eto_link_html = "<em>Not available</em>"

    # Count messaging
    if eto_ok and eto_count == 0:
        eto_count_msg = "0 values (no calculations returned yet — expected if meteo ingestion hasn’t populated the DB for this range)"
    elif eto_count is None:
        eto_count_msg = "Unknown (response schema not recognized)"
    else:
        eto_count_msg = str(eto_count)

    eto_preview_html = ""
    if eto_preview:
        eto_preview_html = f"<pre style='white-space: pre-wrap; max-height: 260px; overflow:auto; border:1px solid #ddd; padding:10px;'>{_safe(eto_preview)}</pre>"

    return f"""
<h2>Irrigation Service Integration</h2>
<p>
  This run includes an integration check against the OpenAgri Irrigation Management Service:
  authentication, parcel availability, and ETo retrieval using the official <code>{_safe(eto_method)}</code> workflow.
</p>

<table border="1" cellpadding="6" cellspacing="0">
  <tr><th align="left">Enabled</th><td>{_safe(enabled)}</td></tr>
  <tr><th align="left">Service URL</th><td>{_safe(base_url)}</td></tr>
  <tr><th align="left">Status</th><td><span style="color:{status_color}; font-weight:bold;">{_safe(status_label)}</span></td></tr>
  <tr><th align="left">Authenticated as</th><td>{_safe(email)}</td></tr>
  <tr><th align="left">Parcels visible to user</th><td>{_safe(parcel_count)}</td></tr>
  <tr><th align="left">Created default parcel this run</th><td>{_safe(created_default)}</td></tr>
</table>

<h3>ETo (FAO-56 Penman–Monteith) — Official get-calculations workflow</h3>
<table border="1" cellpadding="6" cellspacing="0">
  <tr><th align="left">Request status</th><td><span style="color:{eto_color}; font-weight:bold;">{_safe(eto_label)}</span> (HTTP {_safe(eto_status)})</td></tr>
  <tr><th align="left">Location ID</th><td>{_safe(eto_location_id)}</td></tr>
  <tr><th align="left">Date range</th><td>{_safe(eto_from)} → {_safe(eto_to)}</td></tr>
  <tr><th align="left">Returned values</th><td>{_safe(eto_count_msg)}</td></tr>
  <tr><th align="left">Raw response artifact</th><td>{eto_link_html}</td></tr>
</table>

{eto_preview_html}

{notes_html}
""".strip()


def run_report(irrigation_summary: Optional[Dict[str, Any]] = None) -> None:
    print("\n[AgriVision] Generating HTML report...")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    ndvi_meta = _load_json(NDVI_META_PATH)
    grid_meta = _load_json(GRID_META_PATH)

    index_title = _get_index_title(ndvi_meta, grid_meta)
    methodology_html = _render_methodology_section(ndvi_meta)
    grid_meta_html = _render_grid_metadata_section(grid_meta)

    grid_rows = _load_grid_cells()
    grid_table_html = _render_grid_table(index_title=index_title, rows=grid_rows)

    irrigation_html = _render_irrigation_section(irrigation_summary)

    generated_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    artifacts_list_html = "\n".join(
        [
            _render_artifact_link(f"{index_title} Map (PNG)", NDVI_COLOR_PNG),
            _render_artifact_link(f"{index_title} GeoTIFF", NDVI_TIF),
            _render_artifact_link("Grid Overlay (PNG)", GRID_OVERLAY_PNG),
            _render_artifact_link("Grid Cells (CSV)", GRID_CELLS_CSV),
            _render_artifact_link("Grid Categories (CSV)", GRID_CATEGORIES_CSV),
            _render_artifact_link("Index Run Metadata (JSON)", NDVI_META_PATH),
            _render_artifact_link("Grid Run Metadata (JSON)", GRID_META_PATH),
        ]
    )

    html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>AgriVision Vegetation Analysis Report</title>
  <style>
    body {{
      font-family: Arial, sans-serif;
      margin: 40px;
      color: #111;
    }}
    h1, h2 {{
      color: #2a5d34;
    }}
    table {{
      border-collapse: collapse;
      margin-top: 10px;
    }}
    th {{
      background-color: #f0f0f0;
    }}
    code {{
      background-color: #f7f7f7;
      padding: 2px 4px;
    }}
    a {{
      color: #2a5d34;
      text-decoration: none;
    }}
    a:hover {{
      text-decoration: underline;
    }}
  </style>
</head>
<body>

  <h1>AgriVision Vegetation Analysis Report</h1>
  <p><em>Generated at {generated_at}</em></p>

  {methodology_html}

  <h2>Outputs</h2>
  <p>The following products were generated as part of this run.</p>
  <ul>
    {artifacts_list_html}
  </ul>

  <h2>{_safe(index_title)} Visualization</h2>
  {_render_image_if_exists(f"{index_title} Map", NDVI_COLOR_PNG)}

  <h2>Grid-Based Analysis</h2>
  <p>
    Grid statistics are computed by averaging vegetation index values within each grid cell and classifying each cell
    into poor / medium / good using thresholds recorded for this grid run.
  </p>

  {grid_meta_html}

  {_render_image_if_exists("Grid Overlay", GRID_OVERLAY_PNG)}

  <h3>Grid Cells Detail</h3>
  {grid_table_html}

  {irrigation_html}

</body>
</html>
"""

    REPORT_PATH.write_text(html_doc, encoding="utf-8")
    print(f"[AgriVision] Report written to: {REPORT_PATH}")


if __name__ == "__main__":
    run_report()
