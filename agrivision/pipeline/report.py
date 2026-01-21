#!/usr/bin/env python3
"""
agrivision.pipeline.report

Generate the final HTML report for AgriVision.

Features:
- Reads output/ndvi/metadata.json produced by agrivision.pipeline.ndvi
  and includes a "Vegetation Index Methodology" section documenting:
  - index type (index_name)
  - formula
  - sensor source dataset (MAPIR / RGB)
  - band mapping
  - configured classification thresholds (from ndvi metadata)

- Reads output/ndvi/grid_metadata.json produced by agrivision.pipeline.grid
  and includes factual grid classification details:
  - classification mode (fixed vs percentile_fallback)
  - thresholds used

- Restores a grid table in the report by reading output/ndvi/ndvi_grid_cells.csv
  and rendering all cells:
  - supports both mean_index (new) and mean_ndvi (legacy)
  - labels are index-aware (uses index_name in headings)

Usability:
- Uses relative links so the report works when opened locally:
  report:  <output_root>/report_latest.html
  assets:  <output_root>/ndvi/...
- Existence checks for all artifacts
- Handles unreadable/malformed JSON gracefully
- Escapes metadata-derived content for safe HTML rendering
"""

from __future__ import annotations

from pathlib import Path
from datetime import datetime
import json
from json import JSONDecodeError
import html
import csv
from typing import Dict, List

from agrivision.utils.settings import get_project_root, load_config


CONFIG = load_config()
PROJECT_ROOT = get_project_root()

# Output root from config.yaml
OUTPUT_DIR = PROJECT_ROOT / CONFIG["paths"]["output_root"]
REPORT_PATH = OUTPUT_DIR / "report_latest.html"

# NDVI/VegIndex output folder configured in config.yaml (typically output/ndvi)
NDVI_DIR = PROJECT_ROOT / CONFIG["paths"]["ndvi_output"]

# Metadata files
NDVI_META_PATH = NDVI_DIR / "metadata.json"
GRID_META_PATH = NDVI_DIR / "grid_metadata.json"

# Expected artifacts (filenames stable)
NDVI_TIF = NDVI_DIR / "ndvi.tif"
NDVI_COLOR_PNG = NDVI_DIR / "ndvi_color.png"

GRID_OVERLAY_PNG = NDVI_DIR / "ndvi_grid_overlay.png"
GRID_CELLS_CSV = NDVI_DIR / "ndvi_grid_cells.csv"
GRID_CATEGORIES_CSV = NDVI_DIR / "ndvi_grid_categories.csv"


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------
def _rel_to_report(abs_path: Path) -> str:
    """
    Convert an absolute artifact path under OUTPUT_DIR to a relative href/src
    relative to REPORT_PATH (<output_root>/report_latest.html).
    """
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
    """
    Prefer ndvi metadata index_name; fall back to grid metadata; otherwise generic.
    """
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
    if isinstance(band_map, dict) and band_map:
        band_map_str = ", ".join(f"{_safe(k)} = {_safe(v)}" for k, v in band_map.items())
    else:
        band_map_str = "N/A"

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
    """
    Load ndvi_grid_cells.csv into a list of dict rows.
    Supports both schemas:
      - mean_index (new)
      - mean_ndvi (legacy)
    """
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
      {'\n'.join(body)}
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


# ---------------------------------------------------------------------
# Main report generator
# ---------------------------------------------------------------------
def run_report() -> None:
    print("\n[AgriVision] Generating HTML report...")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    ndvi_meta = _load_json(NDVI_META_PATH)
    grid_meta = _load_json(GRID_META_PATH)

    index_title = _get_index_title(ndvi_meta, grid_meta)
    methodology_html = _render_methodology_section(ndvi_meta)
    grid_meta_html = _render_grid_metadata_section(grid_meta)

    grid_rows = _load_grid_cells()
    grid_table_html = _render_grid_table(index_title=index_title, rows=grid_rows)

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
  <p>
    The following products were generated as part of this run.
  </p>

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

</body>
</html>
"""

    REPORT_PATH.write_text(html_doc, encoding="utf-8")
    print(f"[AgriVision] Report written to: {REPORT_PATH}")


if __name__ == "__main__":
    run_report()
