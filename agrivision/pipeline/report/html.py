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


def report_icon(name: str, color: str = "blue", title: str | None = None) -> str:
    labels = {
        "alert": "Alert",
        "calendar": "Date",
        "camera": "Visible imagery",
        "check": "Selected",
        "cloud": "Weather",
        "crosshair": "Risk index",
        "drop": "Water",
        "layers": "Analysis layers",
        "leaf": "Vegetation",
        "location": "Location",
        "notes": "Notes",
        "pest": "Pest pressure",
        "spores": "Disease pressure",
        "sprout": "Growth stage",
        "thermometer": "Temperature",
    }
    paths = {
        "alert": '<path d="M12 7v6"/><path d="M12 17h.01"/><path d="M10.3 3.9 2.4 17.6A2 2 0 0 0 4.1 20h15.8a2 2 0 0 0 1.7-2.4L13.7 3.9a2 2 0 0 0-3.4 0Z"/>',
        "calendar": '<path d="M8 2v4"/><path d="M16 2v4"/><rect x="3" y="5" width="18" height="16" rx="3"/><path d="M3 10h18"/><path d="M8 14h.01"/><path d="M12 14h.01"/><path d="M16 14h.01"/><path d="M8 18h.01"/><path d="M12 18h.01"/>',
        "camera": '<path d="M4 8a3 3 0 0 1 3-3h1.5l1.2-2h4.6l1.2 2H17a3 3 0 0 1 3 3v8a3 3 0 0 1-3 3H7a3 3 0 0 1-3-3Z"/><circle cx="12" cy="12" r="3.5"/>',
        "check": '<path d="m6 12 4 4 8-8"/>',
        "cloud": '<path d="M17.5 18H7a4 4 0 0 1-.6-8 5.8 5.8 0 0 1 11.1-1.7A4.8 4.8 0 0 1 17.5 18Z"/>',
        "crosshair": '<circle cx="12" cy="12" r="7"/><circle cx="12" cy="12" r="2"/><path d="M12 2v4"/><path d="M12 18v4"/><path d="M2 12h4"/><path d="M18 12h4"/>',
        "drop": '<path d="M12 3s6 6.3 6 11a6 6 0 0 1-12 0c0-4.7 6-11 6-11Z"/>',
        "layers": '<path d="m12 3 9 5-9 5-9-5 9-5Z"/><path d="m3 12 9 5 9-5"/><path d="m3 16 9 5 9-5"/>',
        "leaf": '<path d="M20 4C12 4 5 9.6 5 17c0 1.1.2 2.1.6 3C11 19.5 20 14.5 20 4Z"/><path d="M5.6 20C8.2 14.8 11.8 11.5 17 8"/>',
        "location": '<path d="M12 21s7-6.1 7-12a7 7 0 0 0-14 0c0 5.9 7 12 7 12Z"/><circle cx="12" cy="9" r="2.5"/>',
        "notes": '<path d="M7 3h7l4 4v14H7Z"/><path d="M14 3v5h5"/><path d="M9 12h6"/><path d="M9 16h6"/>',
        "pest": '<path d="M8 11a4 4 0 0 1 8 0v5a4 4 0 0 1-8 0Z"/><path d="M9 7 7 4"/><path d="m15 7 2-3"/><path d="M5 12h3"/><path d="M16 12h3"/><path d="M5 16h3"/><path d="M16 16h3"/><path d="M12 11v8"/>',
        "spores": '<circle cx="8" cy="8" r="3"/><circle cx="15" cy="7" r="2"/><circle cx="16" cy="15" r="3"/><circle cx="7" cy="16" r="2"/><circle cx="12" cy="12" r="1.5"/>',
        "sprout": '<path d="M12 21V10"/><path d="M12 13C7 13 4 10 4 5c5 0 8 3 8 8Z"/><path d="M12 11c5 0 8-3 8-8-5 0-8 3-8 8Z"/>',
        "thermometer": '<path d="M14 14.8V5a2 2 0 0 0-4 0v9.8a4 4 0 1 0 4 0Z"/><path d="M12 7v8"/>',
    }
    css_class = f"svg-icon {safe_html(color)}"
    title_html = f"<title>{safe_html(title or labels.get(name, name.title()))}</title>"
    path_html = paths.get(name, paths["notes"])
    return f'<svg class="{css_class}" viewBox="0 0 24 24" role="img" aria-hidden="false">{title_html}{path_html}</svg>'


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
    leaf_icon = report_icon("leaf", "green", "AgriVision")
    camera_icon = report_icon("camera", "blue")
    vegetation_icon = report_icon("leaf", "green", "Vegetation index")
    thermal_icon = report_icon("thermometer", "red")
    risk_icon = report_icon("crosshair", "blue")
    alert_icon = report_icon("alert", "white")
    layers_icon = report_icon("layers", "blue")
    spores_icon = report_icon("spores", "white", "Powdery mildew")
    drop_icon = report_icon("drop", "white", "Downy mildew")
    rot_icon = report_icon("spores", "white", "Botrytis bunch rot")
    risk_target_icon = report_icon("crosshair", "white", "Selected risk profile")
    selected_icon = report_icon("check", "white", "Selected risk profile")
    condition_leaf_icon = report_icon("leaf", "white", "Vegetation index")
    key_conditions_icon = report_icon("cloud", "blue", "Key conditions")
    sprout_icon = report_icon("sprout", "green")
    calendar_icon = report_icon("calendar", "blue")
    vigor_icon = report_icon("leaf", "green", "Vigor status")
    condition_thermal_icon = report_icon("thermometer", "red", "Canopy temperature")
    weather_icon = report_icon("cloud", "blue", "Weather window")
    review_icon = report_icon("calendar", "cyan", "Next review")
    notes_icon = report_icon("notes", "blue")
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
    body.report-embedded {{
      background: white;
    }}
    body.report-embedded .report-page {{
      width: 100%;
      max-width: none;
      min-height: auto;
      padding: 18px 22px 24px;
      box-shadow: none;
    }}
    body.report-embedded .overview {{
      grid-template-columns: minmax(260px, 0.55fr) minmax(480px, 1.1fr) minmax(460px, 1fr);
    }}
    body.report-embedded .image-block img {{
      max-height: none;
    }}
    body.report-embedded .evidence-stack .image-block img {{
      max-height: 255px;
    }}
    body.report-embedded .panel {{
      padding: 13px 15px;
    }}
    body.report-embedded .lower-grid {{
      grid-template-columns: repeat(3, minmax(0, 1fr));
    }}
    .report-header {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 24px;
      border-bottom: 2px solid #1d2f6f;
      padding-bottom: 14px;
      margin-bottom: 16px;
    }}
    h1 {{
      font-size: 38px;
      line-height: 1.05;
      margin: 0 0 8px;
      letter-spacing: 0;
    }}
    .subtitle {{
      color: var(--blue);
      font-size: 18px;
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
      padding: 7px 11px;
      background: white;
      font-weight: 700;
      color: #1d2f6f;
    }}
    .insight-strip {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
      margin-bottom: 16px;
    }}
    .insight {{
      border: 1px solid var(--line);
      border-radius: 12px;
      background: #f8fafc;
      padding: 12px 14px;
    }}
    .insight span {{
      display: block;
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
      margin-bottom: 4px;
      text-transform: uppercase;
    }}
    .insight strong {{
      display: block;
      color: var(--navy);
      font-size: 15px;
      line-height: 1.25;
    }}
    .overview {{
      display: grid;
      grid-template-columns: minmax(230px, 0.52fr) minmax(420px, 1fr) minmax(360px, 0.95fr);
      gap: 18px;
      align-items: start;
    }}
    .side-stack {{ display: grid; gap: 14px; }}
    .evidence-stack {{
      align-content: start;
    }}
    .decision-stack {{
      display: grid;
      gap: 14px;
      align-content: start;
    }}
    .panel {{
      border: 1px solid var(--line);
      border-radius: 10px;
      background: white;
      padding: 14px 16px;
      overflow: hidden;
    }}
    .panel h2, .panel h3 {{
      display: flex;
      align-items: center;
      gap: 10px;
      margin: 0 0 12px;
      font-size: 22px;
      color: var(--navy);
    }}
    .side-stack .panel h2 {{ font-size: 18px; }}
    .icon {{
      display: inline-grid;
      place-items: center;
      width: 30px;
      height: 30px;
      border-radius: 999px;
      padding: 5px;
      background: #edf4ff;
      color: var(--blue);
    }}
    .icon.green {{ background: #e8f8ee; color: var(--green); }}
    .icon.red {{ background: #fff1f0; color: var(--red); }}
    .svg-icon {{
      width: 100%;
      height: 100%;
      display: block;
      fill: none;
      stroke: currentColor;
      stroke-width: 2;
      stroke-linecap: round;
      stroke-linejoin: round;
    }}
    .svg-icon.blue {{ color: var(--blue); }}
    .svg-icon.green {{ color: var(--green); }}
    .svg-icon.red {{ color: var(--red); }}
    .svg-icon.white {{ color: white; }}
    .svg-icon.cyan {{ color: #0ea5e9; }}
    .svg-icon.purple {{ color: #6b46c1; }}
    .svg-icon.brown {{ color: #92400e; }}
    .image-block h3 {{ display: none; }}
    .image-block img {{
      width: 100%;
      height: auto;
      display: block;
      border: 0 !important;
      object-fit: contain;
      max-height: 720px;
    }}
    .evidence-stack .image-block img {{ max-height: 260px; }}
    .image-note {{
      margin-top: 8px;
      font-size: 12px;
      color: var(--muted);
      font-style: italic;
    }}
    .risk-copy {{
      color: #15224d;
      max-width: 760px;
      margin: -4px 0 12px;
      font-style: italic;
    }}
    .legend {{
      display: flex;
      justify-content: center;
      gap: 22px;
      flex-wrap: wrap;
      margin: 14px 0 18px;
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
      border-radius: 10px;
      padding: 14px 16px;
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
      padding: 10px;
    }}
    .alert h3 {{ margin: 2px 0 8px; font-size: 21px; }}
    .alert ul {{ padding-left: 1.2rem; }}
    .lower-grid {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 14px;
      margin-top: 0;
    }}
    .decision-stack .panel h3 {{
      font-size: 15px;
      line-height: 1.25;
    }}
    .decision-stack .panel {{
      padding: 12px;
    }}
    .target-list {{ display: grid; gap: 8px; margin-top: 10px; }}
    .target {{
      display: grid;
      grid-template-columns: 30px 1fr auto;
      align-items: center;
      gap: 10px;
      padding: 7px 6px;
      border-bottom: 1px solid #e7eaf1;
      font-size: 13px;
    }}
    .target.selected {{
      border: 1px solid #ffaaa4;
      background: #fff1f0;
      border-radius: 10px;
      border-bottom-color: #ffaaa4;
    }}
    .target-badge {{
      width: 30px;
      height: 30px;
      display: grid;
      place-items: center;
      border-radius: 999px;
      color: white;
      padding: 8px;
    }}
    .conditions {{
      display: grid;
      grid-template-columns: auto 1fr auto;
      gap: 9px 10px;
      align-items: center;
      font-size: 12px;
    }}
    .condition-icon {{
      display: inline-grid;
      place-items: center;
      width: 24px;
      height: 24px;
      border-radius: 999px;
      background: #eef2ff;
      color: #1d4ed8;
      padding: 5px;
    }}
    .notes ul, .alert ul {{ margin: 0; }}
    .best-practice {{
      border: 1px solid #35a853;
      background: #f1fbf4;
      border-radius: 12px;
      padding: 12px 14px;
      margin-top: 16px;
    }}
    .best-practice .svg-icon {{
      width: 18px;
      height: 18px;
      display: inline-block;
      vertical-align: -3px;
      margin-right: 6px;
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
      .report-header, .overview, .lower-grid, .insight-strip, body.report-embedded .overview {{ grid-template-columns: 1fr; }}
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
      <div class="brand"><span class="icon green">{leaf_icon}</span><span>AgriVision</span><span>ADS</span></div>
      <div class="meta-strip">
        <span class="pill">{generated_at}</span>
        <span class="pill">Drone field run</span>
        <span class="pill">{safe_html(index_title)}</span>
      </div>
    </div>
  </header>

  <section class="insight-strip" aria-label="Report summary">
    <div class="insight">
      <span>Primary layer</span>
      <strong>{safe_html(index_title)}</strong>
    </div>
    <div class="insight">
      <span>Risk focus</span>
      <strong>Scout red and yellow cells first</strong>
    </div>
    <div class="insight">
      <span>Evidence</span>
      <strong>RGB, multispectral, weather, and service outputs</strong>
    </div>
    <div class="insight">
      <span>Recommended action</span>
      <strong>Validate clustered risk zones in the field</strong>
    </div>
  </section>

  <section class="overview">
    <aside class="side-stack evidence-stack">
      <section class="panel">
        <h2><span class="icon">{camera_icon}</span>Visible Orthomosaic</h2>
        <div class="image-block">{visible_image_html}</div>
        <div class="image-note">High-resolution true-color image</div>
      </section>
      <section class="panel">
        <h2><span class="icon green">{vegetation_icon}</span>{safe_html(index_title)}</h2>
        <div class="image-block">{ndvi_color_html}</div>
        <div class="bar"></div>
        <div class="bar-labels"><span>Low vigor</span><span>High vigor</span></div>
      </section>
      <section class="panel">
        <h2><span class="icon red">{thermal_icon}</span>Thermal</h2>
        <div class="image-block">{thermal_image_html}</div>
        <div class="bar thermal-bar"></div>
        <div class="bar-labels"><span>Cold</span><span>Hot</span></div>
        <div class="image-note">MAPIR placeholder until thermal imagery is available</div>
      </section>
    </aside>

    <section class="panel">
      <h2><span class="icon">{risk_icon}</span>Risk Index</h2>
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
    </section>

    <aside class="decision-stack">
      <section class="alert">
        <div class="alert-icon">{alert_icon}</div>
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

      <section class="lower-grid">
        <section class="panel">
          <h3><span class="icon">{layers_icon}</span>Available Analysis Layers / Targets</h3>
          <p class="image-note">AgriVision ADS can combine crop stress, weather suitability, and service outputs for decision support.</p>
          <div class="target-list">
            <div class="target"><span class="target-badge" style="background:#6b46c1;">{spores_icon}</span><strong>Powdery Mildew</strong></div>
            <div class="target"><span class="target-badge" style="background:#0ea5e9;">{drop_icon}</span><strong>Downy Mildew</strong></div>
            <div class="target"><span class="target-badge" style="background:#92400e;">{rot_icon}</span><strong>Botrytis Bunch Rot</strong></div>
            <div class="target selected"><span class="target-badge" style="background:#dc2626;">{risk_target_icon}</span><strong>Selected Risk Profile</strong><span class="target-badge" style="background:#dc2626;">{selected_icon}</span></div>
            <div class="target"><span class="target-badge" style="background:#22c55e;">{condition_leaf_icon}</span><strong>Vegetation Index</strong></div>
          </div>
        </section>

        <section class="panel">
          <h3><span class="icon">{key_conditions_icon}</span>Key Conditions</h3>
          <div class="conditions">
            <span class="condition-icon">{sprout_icon}</span><strong>Seasonal Stage</strong><span>Shoot growth</span>
            <span class="condition-icon">{calendar_icon}</span><strong>Date of Capture</strong><span>{generated_at}</span>
            <span class="condition-icon">{vigor_icon}</span><strong>Vigor Status</strong><span>See grid classes</span>
            <span class="condition-icon">{condition_thermal_icon}</span><strong>Canopy Temperature</strong><span>MAPIR placeholder</span>
            <span class="condition-icon">{weather_icon}</span><strong>Weather Window</strong><span>See service details</span>
            <span class="condition-icon">{review_icon}</span><strong>Next Review</strong><span>After scouting</span>
          </div>
        </section>

        <section class="panel notes">
          <h3><span class="icon">{notes_icon}</span>Notes</h3>
          <ul>
            <li>This report is a decision-support output and should be validated with field scouting.</li>
            <li>Risk values are relative to the current dataset and configured thresholds.</li>
            <li>Thermal display uses MAPIR imagery as a placeholder until thermal capture is available.</li>
          </ul>
        </section>
      </section>
    </aside>
  </section>

  <section class="best-practice">
    <strong>{leaf_icon} Best Practice</strong><br />
    Combine this map with scouting records and recent weather before intervention.
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
