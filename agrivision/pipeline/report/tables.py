"""HTML table renderers for the report stage."""

from __future__ import annotations

from typing import Dict, List

from agrivision.pipeline.report.html import safe_html


def render_grid_table(index_title: str, rows: List[Dict[str, str]]) -> str:
    if not rows:
        return "<p><em>No grid cell CSV available.</em></p>"

    body = []
    for row in rows:
        mean_val = row.get("mean_index")
        if mean_val in (None, ""):
            mean_val = row.get("mean_ndvi", "")

        cls = row.get("class", "")
        row_class = f"class-{cls}" if cls else ""
        body.append(
            f"""
<tr class="{safe_html(row_class)}">
  <td>{safe_html(row.get("cell_id", ""))}</td>
  <td>{safe_html(row.get("row_label", ""))}</td>
  <td>{safe_html(row.get("col_label", ""))}</td>
  <td>{safe_html(mean_val)}</td>
  <td>{safe_html(cls)}</td>
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
        <th align="left">Mean {safe_html(index_title)}</th>
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
