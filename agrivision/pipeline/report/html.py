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
    *,
    location_label: str = "Location not set",
    quality: dict[str, str] | None = None,
) -> str:
    quality = quality or {}
    quality_state = quality.get("quality_state", "N/A")
    source_label = quality.get("source", "N/A")
    valid_pixels = quality.get("valid_pixels", "N/A")
    mean_median = quality.get("mean_median", "N/A")
    thresholds = quality.get("thresholds", "N/A")
    classification = quality.get("classification", "N/A")
    dataset_label = quality.get("dataset", "N/A")
    leaf_icon = report_icon("leaf", "green", "AgriVision")
    camera_icon = report_icon("camera", "navy")
    vegetation_icon = report_icon("leaf", "green", "Vegetation index")
    thermal_icon = report_icon("thermometer", "red")
    risk_icon = report_icon("crosshair", "navy")
    alert_icon = report_icon("alert", "white")
    layers_icon = report_icon("layers", "navy")
    spores_icon = report_icon("spores", "white", "Powdery mildew")
    drop_icon = report_icon("drop", "white", "Downy mildew")
    rot_icon = report_icon("spores", "white", "Botrytis bunch rot")
    risk_target_icon = report_icon("crosshair", "white", "Selected risk profile")
    selected_icon = report_icon("check", "white", "Selected risk profile")
    condition_leaf_icon = report_icon("leaf", "white", "Vegetation index")
    key_conditions_icon = report_icon("cloud", "navy", "Key conditions")
    sprout_icon = report_icon("sprout", "green")
    calendar_icon = report_icon("calendar", "navy")
    location_icon = report_icon("location", "navy")
    vigor_icon = report_icon("leaf", "green", "Vigor status")
    condition_thermal_icon = report_icon("thermometer", "red", "Canopy temperature")
    weather_icon = report_icon("cloud", "green", "Weather window")
    review_icon = report_icon("calendar", "blue", "Next review")
    scout_icon = report_icon("crosshair", "red", "Scout")
    search_icon = report_icon("crosshair", "red", "Inspect")
    rain_icon = report_icon("cloud", "red", "Monitor")
    treatment_icon = report_icon("leaf", "red", "Intervention")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>AgriVision Field Analysis and Risk Mapping</title>
  <style>
    :root {{
      --navy: #07143d;
      --blue: #2563eb;
      --green: #16a34a;
      --red: #f21f18;
      --yellow: #f6c700;
      --line: #dce4ef;
      --muted: #52617b;
      --panel: #ffffff;
      --soft: #f8fafc;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      font-family: "Inter", "Segoe UI", Arial, sans-serif;
      margin: 0;
      color: var(--navy);
      background: #eef3f8;
      line-height: 1.4;
    }}
    .report-page {{
      width: 100%;
      max-width: 1920px;
      margin: 0 auto;
      background: white;
      min-height: 100vh;
      padding: 24px 36px 28px;
      box-shadow: 0 12px 42px rgba(15, 23, 42, 0.1);
    }}
    body.report-embedded {{
      background: white;
    }}
    body.report-embedded .report-page {{
      max-width: none;
      min-height: auto;
      padding: 22px 32px 28px;
      box-shadow: none;
    }}
    .report-header {{
      display: grid;
      grid-template-columns: minmax(420px, 1fr) auto;
      gap: 24px;
      align-items: start;
      padding-bottom: 16px;
      border-bottom: 1px solid #e2e8f0;
    }}
    h1 {{
      font-size: 38px;
      line-height: 1.05;
      margin: 0 0 9px;
      color: #07143d;
      letter-spacing: 0;
    }}
    .subtitle {{
      color: var(--blue);
      font-size: 18px;
      font-weight: 900;
      font-style: italic;
    }}
    .header-side {{
      display: grid;
      justify-items: end;
      gap: 10px;
    }}
    .brand {{
      display: flex;
      justify-content: flex-end;
      align-items: center;
      gap: 8px;
      font-size: 22px;
      font-weight: 900;
      white-space: nowrap;
    }}
    .brand span:last-child {{ color: var(--green); }}
    .meta-row {{
      display: grid;
      grid-template-columns: repeat(2, auto);
      border: 1px solid var(--line);
      border-radius: 10px;
      background: white;
      overflow: hidden;
    }}
    .pill {{
      display: inline-flex;
      align-items: center;
      gap: 9px;
      min-height: 40px;
      padding: 0 16px;
      color: #16234f;
      font-weight: 800;
      border-left: 1px solid var(--line);
      white-space: nowrap;
    }}
    .pill .svg-icon {{
      width: 18px;
      height: 18px;
      flex: 0 0 auto;
    }}
    .pill:first-child {{ border-left: 0; }}
    .report-grid {{
      display: grid;
      grid-template-columns: minmax(330px, 0.75fr) minmax(620px, 1.35fr) minmax(330px, 0.7fr);
      gap: 18px;
      margin-top: 14px;
      align-items: stretch;
    }}
    .side-stack, .right-stack {{
      display: grid;
      gap: 14px;
      align-content: start;
    }}
    .panel {{
      border: 1px solid var(--line);
      border-radius: 10px;
      background: var(--panel);
      padding: 15px 16px;
      overflow: hidden;
    }}
    .panel h2, .panel h3 {{
      display: flex;
      align-items: center;
      gap: 10px;
      margin: 0 0 12px;
      color: var(--navy);
      font-size: 18px;
      line-height: 1.2;
    }}
    .risk-panel h2 {{
      font-size: 21px;
    }}
    .icon {{
      display: inline-grid;
      place-items: center;
      width: 28px;
      height: 28px;
      border-radius: 999px;
      padding: 5px;
      color: var(--navy);
    }}
    .icon.green {{ color: var(--green); background: #e8f8ee; }}
    .icon.red {{ color: var(--red); background: #fff1f0; }}
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
    .svg-icon.navy {{ color: var(--navy); }}
    .image-block h3 {{ display: none; }}
    .image-block img {{
      width: 100%;
      height: auto;
      display: block;
      border: 0 !important;
      object-fit: contain;
    }}
    .side-stack .image-block img {{
      max-height: 260px;
    }}
    .risk-panel .image-block img {{
      max-height: 620px;
    }}
    body.report-embedded .side-stack .image-block img {{
      max-height: 260px;
    }}
    body.report-embedded .risk-panel .image-block img {{
      max-height: 620px;
    }}
    .image-note {{
      margin-top: 8px;
      font-size: 12px;
      color: var(--muted);
      font-style: italic;
    }}
    .risk-copy {{
      color: #13204a;
      margin: -4px 0 12px;
      font-size: 14px;
      max-width: 760px;
    }}
    .legend {{
      display: flex;
      justify-content: center;
      gap: 34px;
      flex-wrap: wrap;
      margin-top: 14px;
      font-weight: 800;
      font-size: 14px;
    }}
    .legend span {{ display: inline-flex; align-items: center; gap: 8px; }}
    .dot {{ width: 16px; height: 16px; border-radius: 999px; display: inline-block; }}
    .dot.blue {{ background: #2563eb; }}
    .dot.green {{ background: #16a34a; }}
    .dot.yellow {{ background: var(--yellow); }}
    .dot.red {{ background: var(--red); }}
    .bar {{
      height: 12px;
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
    .alert-panel {{ margin-top: 14px; }}
    .alert-title {{
      display: flex;
      align-items: center;
      gap: 13px;
      margin-bottom: 12px;
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
      flex: 0 0 auto;
    }}
    .alert-title h2 {{
      margin: 0;
      font-size: 20px;
    }}
    .alert-list {{
      border: 1px solid #ffaaa4;
      background: #fff8f7;
      border-radius: 12px;
      padding: 13px 15px;
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 11px 14px;
    }}
    .alert-item {{
      display: grid;
      grid-template-columns: 42px minmax(0, 1fr);
      align-items: center;
      gap: 14px;
      color: #13204a;
      font-size: 13px;
    }}
    .alert-symbol {{
      width: 42px;
      height: 42px;
      border-radius: 999px;
      display: grid;
      place-items: center;
      border: 1px solid #ffaaa4;
      background: white;
      color: var(--red);
      padding: 9px;
    }}
    .info-grid {{
      display: grid;
      grid-template-columns: 1fr;
      gap: 10px;
    }}
    .info-grid .panel {{
      padding: 13px;
    }}
    .info-grid h3 {{
      font-size: 16px;
    }}
    .target-list {{ display: grid; gap: 8px; }}
    .target {{
      display: grid;
      grid-template-columns: 32px 1fr auto;
      align-items: center;
      gap: 8px;
      padding: 7px 8px;
      border-bottom: 1px solid #e7eaf1;
      font-size: 13px;
      font-weight: 800;
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
      grid-template-columns: 24px minmax(0, 1fr) auto;
      gap: 9px 9px;
      align-items: center;
      font-size: 12px;
    }}
    .condition-icon {{
      display: inline-grid;
      place-items: center;
      width: 22px;
      height: 22px;
      color: var(--navy);
    }}
    .condition-icon .svg-icon {{
      width: 20px;
      height: 20px;
    }}
    .bottom-grid {{
      display: grid;
      grid-template-columns: minmax(270px, 0.8fr) minmax(520px, 1.7fr) minmax(280px, 0.8fr);
      gap: 8px;
      margin-top: 16px;
    }}
    .best-practice {{
      border-color: #b7e7c5;
      background: #f2fbf5;
    }}
    .best-practice p {{
      margin: 0;
      color: #13204a;
      font-size: 13px;
    }}
    .quality-grid {{
      display: grid;
      grid-template-columns: repeat(6, minmax(0, 1fr));
      gap: 8px;
    }}
    .quality-card, .run-info-row {{
      border: 1px solid var(--line);
      border-radius: 9px;
      padding: 9px 11px;
      background: white;
      display: grid;
      gap: 4px;
      min-height: 54px;
    }}
    .quality-card span, .run-info-row span {{
      color: var(--muted);
      font-size: 12px;
    }}
    .quality-card strong, .run-info-row strong {{
      font-size: 13px;
      color: var(--navy);
    }}
    .ok-pill {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      border: 1px solid #86efac;
      border-radius: 999px;
      background: #dcfce7;
      color: #166534;
      font-weight: 900;
      min-height: 24px;
    }}
    .run-info {{
      display: grid;
      gap: 8px;
    }}
    .details {{
      margin-top: 18px;
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 18px;
      background: linear-gradient(180deg, #fbfdff 0%, #f8fafc 100%);
    }}
    .details h2 {{
      display: flex;
      align-items: center;
      margin: 18px 0 10px;
      padding: 11px 13px;
      border: 1px solid #d9e4f1;
      border-radius: 10px;
      background: white;
      color: var(--navy);
      font-size: 20px;
      box-shadow: 0 8px 20px rgba(15, 23, 42, 0.04);
    }}
    .details h2:first-child {{ margin-top: 0; }}
    .details h3 {{
      margin: 16px 0 8px;
      color: #13204a;
      font-size: 16px;
    }}
    .details h4 {{
      margin: 14px 0 8px;
      color: #13204a;
      font-size: 14px;
    }}
    .details p {{
      margin: 8px 0 12px;
      color: #334155;
    }}
    .details ul {{
      margin: 8px 0 14px;
      padding-left: 22px;
      color: #334155;
    }}
    table {{
      width: 100%;
      border-collapse: separate;
      border-spacing: 0;
      margin-top: 10px;
      overflow: hidden;
      border: 1px solid #d9e4f1;
      border-radius: 10px;
      background: white;
    }}
    th, td {{
      padding: 9px 11px;
      border: 0;
      border-bottom: 1px solid #e7eef7;
      text-align: left;
      vertical-align: top;
    }}
    tr:last-child th, tr:last-child td {{ border-bottom: 0; }}
    th {{
      background-color: #f1f6fb;
      color: #42526d;
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.02em;
    }}
    code {{
      background-color: #eef4fa;
      border: 1px solid #dbe6f2;
      border-radius: 5px;
      padding: 2px 5px;
      color: #0f2558;
    }}
    pre {{
      border-color: #d9e4f1 !important;
      border-radius: 10px;
      background: #07143d !important;
      color: #e7eef7;
    }}
    a {{ color: #1d4ed8; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .subtle-card {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      margin: 12px 0;
      background: #fafafa;
    }}
    @media (max-width: 1300px) {{
      .report-grid, .bottom-grid {{ grid-template-columns: 1fr; }}
      .quality-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
    }}
    @media (max-width: 760px) {{
      .report-header {{ grid-template-columns: 1fr; }}
      .report-header {{ display: grid; }}
      .header-side {{ justify-items: start; }}
      .meta-row, .quality-grid, .alert-list {{ grid-template-columns: 1fr; }}
      h1 {{ font-size: 32px; }}
      .report-page, body.report-embedded .report-page {{ padding: 18px; }}
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
    <div class="header-side">
      <div class="brand"><span class="icon green">{leaf_icon}</span><span>AgriVision</span><span>ADS</span></div>
      <div class="meta-row">
        <span class="pill">{calendar_icon}{generated_at}</span>
        <span class="pill">{location_icon}{safe_html(location_label)}</span>
      </div>
    </div>
  </header>

  <section class="report-grid">
    <aside class="side-stack">
      <section class="panel">
        <h2><span class="icon">{camera_icon}</span>Visible Orthomosaic</h2>
        <div class="image-block">{visible_image_html}</div>
        <div class="image-note">High-resolution true-color image</div>
      </section>
      <section class="panel">
        <h2><span class="icon green">{vegetation_icon}</span>{safe_html(index_title)}</h2>
        <div class="image-block">{ndvi_color_html}</div>
        <div class="bar"></div>
        <div class="bar-labels"><span>Low Vigor</span><span>High Vigor</span></div>
      </section>
      <section class="panel">
        <h2><span class="icon red">{thermal_icon}</span>Thermal</h2>
        <div class="image-block">{thermal_image_html}</div>
        <div class="bar thermal-bar"></div>
        <div class="bar-labels"><span>Cold</span><span>Hot</span></div>
        <div class="image-note">MAPIR placeholder until thermal imagery is available</div>
      </section>
    </aside>

    <section class="panel risk-panel">
      <h2><span class="icon">{risk_icon}</span>Risk Index</h2>
      <p class="risk-copy">
        Integrated risk map combining vegetation vigor, canopy temperature, weather suitability,
        and historical pressure indicators.
      </p>
      <div class="image-block">{grid_overlay_html}</div>
      <div class="legend">
        <span><i class="dot blue"></i>Blue = Very Low</span>
        <span><i class="dot green"></i>Green = Low</span>
        <span><i class="dot yellow"></i>Yellow = Medium</span>
        <span><i class="dot red"></i>Red = High</span>
      </div>
      <section class="panel alert-panel">
        <div class="alert-title">
          <div class="alert-icon">{alert_icon}</div>
          <h2>Alert Summary</h2>
        </div>
        <div class="alert-list">
          <div class="alert-item"><span class="alert-symbol">{scout_icon}</span><span>High risk concentrated in central and eastern blocks.</span></div>
          <div class="alert-item"><span class="alert-symbol">{search_icon}</span><span>Inspect high-risk cells and prioritize scouting.</span></div>
          <div class="alert-item"><span class="alert-symbol">{rain_icon}</span><span>Monitor conditions and revisit after key weather events.</span></div>
          <div class="alert-item"><span class="alert-symbol">{treatment_icon}</span><span>Plan targeted intervention in high-risk and adjacent yellow zones.</span></div>
        </div>
      </section>
    </section>

    <aside class="right-stack">
      <section class="info-grid">
        <section class="panel">
          <h3><span class="icon">{layers_icon}</span>Available Analysis Layers / Targets</h3>
          <p class="image-note">AgriVision ADS can generate disease or pest-specific layers to support decision-making and risk management.</p>
          <div class="target-list">
            <div class="target"><span class="target-badge" style="background:#6b46c1;">{spores_icon}</span><strong>Powdery Mildew</strong></div>
            <div class="target"><span class="target-badge" style="background:#2f80d0;">{drop_icon}</span><strong>Downy Mildew</strong></div>
            <div class="target"><span class="target-badge" style="background:#8a5a2f;">{rot_icon}</span><strong>Botrytis Bunch Rot</strong></div>
            <div class="target selected"><span class="target-badge" style="background:#f21f18;">{risk_target_icon}</span><strong>Selected Risk Profile</strong><span class="target-badge" style="background:#f21f18;">{selected_icon}</span></div>
            <div class="target"><span class="target-badge" style="background:#22c55e;">{condition_leaf_icon}</span><strong>Vine Mealybug</strong></div>
          </div>
        </section>

        <section class="panel">
          <h3><span class="icon">{key_conditions_icon}</span>Key Conditions</h3>
          <div class="conditions">
            <span class="condition-icon">{sprout_icon}</span><strong>Seasonal Stage</strong><span>Shoot Growth</span>
            <span class="condition-icon">{calendar_icon}</span><strong>Date of Capture</strong><span>{generated_at}</span>
            <span class="condition-icon">{vigor_icon}</span><strong>Vigor Status</strong><span>Moderate-High</span>
            <span class="condition-icon">{condition_thermal_icon}</span><strong>Canopy Temperature</strong><span>Variable</span>
            <span class="condition-icon">{weather_icon}</span><strong>Weather Window</strong><span>Favorable</span>
            <span class="condition-icon">{review_icon}</span><strong>Next Review</strong><span>After scouting</span>
          </div>
        </section>
      </section>
    </aside>
  </section>

  <section class="bottom-grid">
    <section class="panel best-practice">
      <h3><span class="icon green">{leaf_icon}</span>Best Practice</h3>
      <p>Combine this map with field scouting and historical records to guide proactive risk management and timely intervention.</p>
    </section>

    <section class="panel">
      <h3>Result Quality</h3>
      <div class="quality-grid">
        <div class="quality-card"><span>Quality</span><strong class="ok-pill">{safe_html(quality_state)}</strong></div>
        <div class="quality-card"><span>Source</span><strong>{safe_html(source_label)}</strong></div>
        <div class="quality-card"><span>Valid Pixels</span><strong>{safe_html(valid_pixels)}</strong></div>
        <div class="quality-card"><span>Mean / Median</span><strong>{safe_html(mean_median)}</strong></div>
        <div class="quality-card"><span>Thresholds</span><strong>{safe_html(thresholds)}</strong></div>
        <div class="quality-card"><span>Classification</span><strong>{safe_html(classification)}</strong></div>
      </div>
    </section>

    <section class="panel run-info">
      <h3>Run Information</h3>
      <div class="run-info-row"><span>Created</span><strong>{generated_at}</strong></div>
      <div class="run-info-row"><span>Source Dataset</span><strong>{safe_html(dataset_label)}</strong></div>
    </section>
  </section>

  <section class="details">
    <h2>Detailed Analysis</h2>
    {weather_html}
    {methodology_html}
    <h2>Outputs</h2>
    <ul>{artifacts_list_html}</ul>
    <h2>Grid-Based Analysis</h2>
    {grid_meta_html}
    <h3>Grid Cells Detail</h3>
    {grid_table_html}
    {irrigation_html}
    {pdm_html}
  </section>
</main>
</body>
</html>
"""
