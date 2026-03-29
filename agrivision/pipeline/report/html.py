"""Low-level HTML helpers and final document assembly for the report stage."""

from __future__ import annotations

import html
from pathlib import Path

from agrivision.pipeline.report.assets import rel_to_report


def safe_html(value: object) -> str:
    if value is None:
        return ""
    return html.escape(str(value), quote=True)



def render_artifact_link(label: str, path: Path, output_dir: Path) -> str:
    if path.exists():
        href = rel_to_report(path, output_dir)
        return (
            f'<li><strong>{safe_html(label)}:</strong> '
            f'<a href="{safe_html(href)}">{safe_html(href)}</a></li>'
        )
    return f"<li><strong>{safe_html(label)}:</strong> <em>Not found</em></li>"



def render_image_if_exists(title: str, path: Path, output_dir: Path) -> str:
    if not path.exists():
        return f"<p><em>{safe_html(title)} not found.</em></p>"
    src = rel_to_report(path, output_dir)
    return f"""
<h3>{safe_html(title)}</h3>
<img src="{safe_html(src)}" alt="{safe_html(title)}" style="max-width: 100%; height: auto; border: 1px solid #ddd;" />
""".strip()



def build_report_html(
    generated_at: str,
    index_title: str,
    weather_html: str,
    methodology_html: str,
    artifacts_list_html: str,
    ndvi_color_html: str,
    grid_meta_html: str,
    grid_overlay_html: str,
    grid_table_html: str,
    irrigation_html: str,
) -> str:
    return f"""<!DOCTYPE html>
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
    .subtle-card {{
      border: 1px solid #ddd;
      border-radius: 6px;
      padding: 12px;
      margin: 12px 0;
      background: #fafafa;
    }}
  </style>
</head>
<body>

  <h1>AgriVision Vegetation Analysis Report</h1>
  <p><em>Generated at {generated_at}</em></p>

  {weather_html}

  {methodology_html}

  <h2>Outputs</h2>
  <p>The following products were generated as part of this run.</p>
  <ul>
    {artifacts_list_html}
  </ul>

  <h2>{safe_html(index_title)} Visualization</h2>
  {ndvi_color_html}

  <h2>Grid-Based Analysis</h2>
  <p>
    Grid statistics are computed by averaging vegetation index values within each grid cell and classifying each cell
    into poor / medium / good using thresholds recorded for this grid run.
  </p>

  {grid_meta_html}

  {grid_overlay_html}

  <h3>Grid Cells Detail</h3>
  {grid_table_html}

  {irrigation_html}

</body>
</html>
"""
