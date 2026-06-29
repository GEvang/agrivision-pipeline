from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, HTMLResponse

from agrivision.app import dependencies as deps

router = APIRouter()
NO_CACHE_HEADERS = {"Cache-Control": "no-store, max-age=0"}


def _resolve_artifact_path(value: str) -> Path:
    path = Path(value)
    if path.exists():
        return path
    normalized = value.replace('\\', '/')
    marker = '/agrivision-pipeline/'
    if marker in normalized:
        relative = normalized.split(marker, 1)[1]
        candidate = get_project_root() / relative
        if candidate.exists():
            return candidate
    return path


def _strip_embedded_report_chrome(html: str) -> str:
    return re.sub(r'<header class="report-appbar">.*?</header>\s*', '', html, count=1, flags=re.DOTALL)


@router.get('/artifacts/{run_id}/report-assets/{asset_path:path}')
def report_asset(run_id: str, asset_path: str) -> FileResponse:
    workspace = deps.run_service.workspace_for_run(run_id)
    output_root = workspace.output_root.resolve()
    candidate = (output_root / asset_path).resolve()
    try:
        candidate.relative_to(output_root)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail='Artifact not found.') from exc
    if not candidate.exists() or not candidate.is_file():
        raise HTTPException(status_code=404, detail='Artifact file missing.')
    return FileResponse(candidate, headers=NO_CACHE_HEADERS)


@router.get('/artifacts/{run_id}/{artifact_name}')
def artifact(run_id: str, artifact_name: str, embedded: bool = False):
    run = deps.run_service.load_run(run_id)
    report = deps.report_service.get_report(run_id)
    options = {
        'report': report.report_path,
        'orthophoto': report.orthophoto_path,
        'orthophoto-rgb': run.outputs.get('orthophoto_rgb'),
        'orthophoto-mapir': run.outputs.get('orthophoto_mapir'),
        'orthophoto-thermal': run.outputs.get('orthophoto_thermal'),
        'preview': report.preview_path,
        'log': run.logs_path,
    }
    path = options.get(artifact_name)
    if not path:
        raise HTTPException(status_code=404, detail='Artifact not found.')
    resolved = _resolve_artifact_path(path)
    if not resolved.exists():
        raise HTTPException(status_code=404, detail='Artifact file missing.')
    if artifact_name == 'report':
        html = resolved.read_text(encoding='utf-8')
        base_tag = f'<base href="/artifacts/{run_id}/report-assets/">'
        if '</head>' in html:
            html = html.replace('</head>', f'  {base_tag}\n</head>', 1)
        else:
            html = base_tag + html
        if embedded:
            html = html.replace('<body>', '<body class="report-embedded">', 1)
            html = _strip_embedded_report_chrome(html)
        return HTMLResponse(content=html, headers=NO_CACHE_HEADERS)
    return FileResponse(resolved, headers=NO_CACHE_HEADERS)


@router.get('/runs/{run_id}/package')
def run_package(run_id: str) -> FileResponse:
    try:
        package_path = deps.export_service.build_package(run_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail='Run package could not be built.') from exc
    return FileResponse(
        package_path,
        media_type='application/zip',
        filename=f'{run_id}-package.zip',
    )
