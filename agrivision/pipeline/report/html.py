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
    visible_image_html: str,
    ndvi_color_html: str,
    thermal_image_html: str,
    grid_meta_html: str,
    grid_overlay_html: str,
    grid_table_html: str,
    irrigation_html: str,
    pdm_html: str,
) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>AgriVision Field Analysis and Risk Mapping</title>
  <style>
    :root {{
      --navy: #071a4d;
      --blue: #2563eb;
      --green: #16a34a;
      --red: #ef3124;
      --yellow: #f7c600;
      --line: #d8dee9;
      --muted: #5f6b85;
      --soft: #f8fafc;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      font-family: "Inter", "Segoe UI", Arial, sans-serif;
      margin: 0;
      color: var(--navy);
      background: #f4f7fb;
      line-height: 1.45;
    }}
    .report-page {{
      max-width: 1180px;
      margin: 0 auto;
      background: white;
      min-height: 100vh;
      padding: 30px 34px 28px;
      box-shadow: 0 12px 42px rgba(15, 23, 42, 0.12);
    }}
    .report-header {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 24px;
      border-bottom: 2px solid #1d2f6f;
      padding-bottom: 16px;
      margin-bottom: 22px;
    }}
    h1 {{
      font-size: 42px;
      line-height: 1.05;
      margin: 0 0 8px;
      letter-spacing: 0;
    }}
    .subtitle {{
      color: var(--blue);
      font-size: 21px;
      font-weight: 800;
      font-style: italic;
    }}
    .brand {{
      display: flex;
      justify-content: flex-end;
      align-items: center;
      gap: 8px;
      font-size: 24px;
      font-weight: 900;
      white-space: nowrap;
    }}
    .brand-mark {{
      color: var(--green);
      border: 2px solid var(--green);
      border-radius: 999px;
      padding: 2px 8px;
      font-size: 16px;
    }}
    .brand span:last-child {{ color: var(--green); }}
    .meta-strip {{
      display: flex;
      gap: 10px;
      justify-content: flex-end;
      flex-wrap: wrap;
      margin-top: 14px;
    }}
    .pill {{
      border: 1px solid var(--line);
      border-radius: 10px;
      padding: 8px 12px;
      background: white;
      font-weight: 700;
      color: #1d2f6f;
    }}
    .overview {{
      display: grid;
      grid-template-columns: 0.58fr 1fr;
      gap: 24px;
      align-items: stretch;
    }}
    .side-stack {{ display: grid; gap: 14px; }}
    .panel {{
      border: 1px solid var(--line);
      border-radius: 14px;
      background: white;
      padding: 16px 18px;
      overflow: hidden;
    }}
    .panel h2, .panel h3 {{
      display: flex;
      align-items: center;
      gap: 10px;
      margin: 0 0 12px;
      font-size: 24px;
      color: var(--navy);
    }}
    .side-stack .panel h2 {{ font-size: 20px; }}
    .icon {{
      display: inline-grid;
      place-items: center;
      min-width: 30px;
      height: 30px;
      border-radius: 999px;
      padding: 0 7px;
      background: #edf4ff;
      color: var(--blue);
      font-size: 12px;
      font-weight: 900;
    }}
    .icon.green {{ background: #e8f8ee; color: var(--green); }}
    .icon.red {{ background: #fff1f0; color: var(--red); }}
    .image-block h3 {{ display: none; }}
    .image-block img {{
      width: 100%;
      height: auto;
      display: block;
      border: 0 !important;
      object-fit: contain;
      max-height: 760px;
    }}
    .image-note {{
      margin-top: 8px;
      font-size: 12px;
      color: var(--muted);
      font-style: italic;
    }}
    .risk-copy {{
      color: #15224d;
      max-width: 560px;
      margin: -4px 0 12px;
      font-style: italic;
    }}
    .legend {{
      display: flex;
      justify-content: center;
      gap: 28px;
      flex-wrap: wrap;
      margin: 16px 0 24px;
      font-weight: 700;
    }}
    .legend span {{ display: inline-flex; align-items: center; gap: 8px; }}
    .dot {{ width: 18px; height: 18px; border-radius: 999px; display: inline-block; }}
    .dot.blue {{ background: #2563eb; }}
    .dot.green {{ background: #32a852; }}
    .dot.yellow {{ background: var(--yellow); }}
    .dot.red {{ background: var(--red); }}
    .bar {{
      height: 14px;
      border-radius: 999px;
      background: linear-gradient(90deg, #ef3124, #f7c600, #19a64a);
      margin-top: 8px;
    }}
    .thermal-bar {{
      background: linear-gradient(90deg, #1d4ed8, #67d2ff, #f5e642, #f97316, #dc2626);
    }}
    .bar-labels {{
      display: flex;
      justify-content: space-between;
      color: var(--muted);
      font-size: 12px;
      margin-top: 5px;
    }}
    .alert {{
      border: 1px solid #ffaaa4;
      background: #fff8f7;
      border-radius: 14px;
      padding: 18px 22px;
      margin-top: 20px;
      display: grid;
      grid-template-columns: 46px 1fr;
      gap: 14px;
    }}
    .alert-icon {{
      width: 46px;
      height: 46px;
      border-radius: 999px;
      display: grid;
      place-items: center;
      background: var(--red);
      color: white;
      font-size: 25px;
      font-weight: 900;
    }}
    .alert h3 {{ margin: 2px 0 8px; font-size: 21px; }}
    .lower-grid {{
      display: grid;
      grid-template-columns: 1.08fr 0.92fr 1fr;
      gap: 18px;
      margin-top: 22px;
    }}
    .target-list {{ display: grid; gap: 8px; margin-top: 10px; }}
    .target {{
      display: grid;
      grid-template-columns: 36px 1fr auto;
      align-items: center;
      gap: 10px;
      padding: 8px 10px;
      border-bottom: 1px solid #e7eaf1;
    }}
    .target.selected {{
      border: 1px solid #ffaaa4;
      background: #fff1f0;
      border-radius: 10px;
      border-bottom-color: #ffaaa4;
    }}
    .target-badge {{
      width: 34px;
      height: 34px;
      display: grid;
      place-items: center;
      border-radius: 999px;
      color: white;
      font-weight: 900;
    }}
    .conditions {{
      display: grid;
      grid-template-columns: auto 1fr auto;
      gap: 10px 12px;
      align-items: center;
      font-size: 14px;
    }}
    .condition-icon {{
      display: inline-grid;
      place-items: center;
      width: 24px;
      height: 24px;
      border-radius: 999px;
      background: #eef2ff;
      color: #1d4ed8;
      font-size: 12px;
      font-weight: 900;
    }}
    .notes ul, .alert ul {{ margin: 0; }}
    .best-practice {{
      border: 1px solid #35a853;
      background: #f1fbf4;
      border-radius: 12px;
      padding: 12px 14px;
      margin-top: 12px;
    }}
    .details {{
      margin-top: 24px;
      border-top: 2px solid #e7eaf1;
      padding-top: 20px;
    }}
    .details h2 {{ color: var(--navy); }}
    table {{ border-collapse: collapse; margin-top: 10px; }}
    th {{ background-color: #f0f4f8; }}
    code {{ background-color: #f7f7f7; padding: 2px 4px; }}
    a {{ color: #1d4ed8; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .subtle-card {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      margin: 12px 0;
      background: #fafafa;
    }}
    .footer {{
      display: flex;
      gap: 16px;
      align-items: center;
      margin-top: 24px;
      color: var(--muted);
      font-size: 13px;
      font-style: italic;
    }}
    @media (max-width: 920px) {{
      .report-page {{ padding: 20px; }}
      .report-header, .overview, .lower-grid {{ grid-template-columns: 1fr; }}
      .brand, .meta-strip {{ justify-content: flex-start; }}
      h1 {{ font-size: 34px; }}
    }}
  </style>
</head>
<body>
<main class="report-page">
  <header class="report-header">
    <div>
      <h1>Field Analysis and Risk Mapping</h1>
      <div class="subtitle">AgriVision Output - Disease / Pest Risk Mapping</div>
    </div>
    <div>
      <div class="brand"><span class="brand-mark">leaf</span><span>AgriVision</span><span>ADS</span></div>
      <div class="meta-strip">
        <span class="pill">{generated_at}</span>
        <span class="pill">Drone field run</span>
        <span class="pill">{safe_html(index_title)}</span>
      </div>
    </div>
  </header>

  <section class="overview">
    <aside class="side-stack">
      <section class="panel">
        <h2><span class="icon">RGB</span>Visible Orthomosaic</h2>
        <div class="image-block">{visible_image_html}</div>
        <div class="image-note">High-resolution true-color image</div>
      </section>
      <section class="panel">
        <h2><span class="icon green">VI</span>{safe_html(index_title)}</h2>
        <div class="image-block">{ndvi_color_html}</div>
        <div class="bar"></div>
        <div class="bar-labels"><span>Low vigor</span><span>High vigor</span></div>
      </section>
      <section class="panel">
        <h2><span class="icon red">TH</span>Thermal</h2>
        <div class="image-block">{thermal_image_html}</div>
        <div class="bar thermal-bar"></div>
        <div class="bar-labels"><span>Cold</span><span>Hot</span></div>
        <div class="image-note">MAPIR placeholder until thermal imagery is available</div>
      </section>
    </aside>

    <section class="panel">
      <h2><span class="icon">RI</span>Risk Index</h2>
      <p class="risk-copy">
        Integrated risk map combining vegetation vigor, multispectral condition, weather suitability,
        and available pest or disease indicators.
      </p>
      <div class="image-block">{grid_overlay_html}</div>
      <div class="legend">
        <span><i class="dot blue"></i>Blue = Very Low</span>
        <span><i class="dot green"></i>Green = Low</span>
        <span><i class="dot yellow"></i>Yellow = Medium</span>
        <span><i class="dot red"></i>Red = High</span>
      </div>
      <section class="alert">
        <div class="alert-icon">!</div>
        <div>
          <h3>Alert Summary</h3>
          <ul>
            <li>Review red and yellow grid cells first during field scouting.</li>
            <li>Validate risk zones against visual crop condition and recent weather.</li>
            <li>Prioritize intervention around clustered high-risk or low-vigor blocks.</li>
            <li>Re-run analysis after major weather events or new imagery.</li>
          </ul>
        </div>
      </section>
    </section>
  </section>

  <section class="lower-grid">
    <section class="panel">
      <h3><span class="icon">LY</span>Available Analysis Layers / Targets</h3>
      <p class="image-note">AgriVision ADS can combine crop stress, weather suitability, and service outputs for decision support.</p>
      <div class="target-list">
        <div class="target"><span class="target-badge" style="background:#6b46c1;">PM</span><strong>Powdery Mildew</strong></div>
        <div class="target"><span class="target-badge" style="background:#0ea5e9;">DM</span><strong>Downy Mildew</strong></div>
        <div class="target"><span class="target-badge" style="background:#92400e;">BR</span><strong>Botrytis Bunch Rot</strong></div>
        <div class="target selected"><span class="target-badge" style="background:#dc2626;">RI</span><strong>Selected Risk Profile</strong><span>OK</span></div>
        <div class="target"><span class="target-badge" style="background:#22c55e;">VI</span><strong>Vegetation Index</strong></div>
      </div>
    </section>

    <section class="panel">
      <h3><span class="icon">KC</span>Key Conditions</h3>
      <div class="conditions">
        <span class="condition-icon">S</span><strong>Seasonal Stage</strong><span>Shoot growth</span>
        <span class="condition-icon">D</span><strong>Date of Capture</strong><span>{generated_at}</span>
        <span class="condition-icon">V</span><strong>Vigor Status</strong><span>See grid classes</span>
        <span class="condition-icon">T</span><strong>Canopy Temperature</strong><span>MAPIR placeholder</span>
        <span class="condition-icon">W</span><strong>Weather Window</strong><span>See service details</span>
        <span class="condition-icon">R</span><strong>Next Review</strong><span>After scouting</span>
      </div>
    </section>

    <section class="panel notes">
      <h3><span class="icon">NT</span>Notes</h3>
      <ul>
        <li>This report is a decision-support output and should be validated with field scouting.</li>
        <li>Risk values are relative to the current dataset and configured thresholds.</li>
        <li>Thermal display uses MAPIR imagery as a placeholder until thermal capture is available.</li>
      </ul>
      <div class="best-practice">
        <strong>Best Practice</strong><br />
        Combine this map with scouting records and recent weather before intervention.
      </div>
    </section>
  </section>

  <section class="details">
    <h2>Detailed Analysis</h2>
    {weather_html}

    {methodology_html}

    <h2>Outputs</h2>
    <p>The following products were generated as part of this run.</p>
    <ul>
      {artifacts_list_html}
    </ul>

    <h2>Grid-Based Analysis</h2>
    <p>
      Grid statistics are computed by averaging vegetation index values within each grid cell and classifying each cell
      into poor / medium / good using thresholds recorded for this grid run.
    </p>

    {grid_meta_html}

    <h3>Grid Cells Detail</h3>
    {grid_table_html}

    {irrigation_html}

    {pdm_html}
  </section>

  <footer class="footer">
    <span>AgriVision ADS - Advanced Decision Support for Smart Agriculture</span>
    <span>|</span>
    <span>Precision insights. Healthier fields. Better decisions.</span>
  </footer>
</main>
</body>
</html>
"""
