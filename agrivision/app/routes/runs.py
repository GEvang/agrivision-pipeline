from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from agrivision.app import dependencies as deps
from agrivision.app.schemas.runs import RunCreateRequest
from agrivision.services.pdm.catalog import PDM_MODEL_CATALOG

router = APIRouter()

ORTHOPHOTO_PRESETS = [
    {
        'key': 'preview',
        'label': 'Preview',
        'resolution_cm': 8,
        'reduce_images': True,
        'description': 'Fastest run for checking image coverage.',
    },
    {
        'key': 'balanced',
        'label': 'Balanced (recommended)',
        'resolution_cm': 3,
        'reduce_images': True,
        'description': 'Good default for dashboard analysis and normal field reports.',
    },
    {
        'key': 'high',
        'label': 'High detail',
        'resolution_cm': 2,
        'reduce_images': False,
        'description': 'More detail with longer ODM processing time.',
    },
    {
        'key': 'maximum',
        'label': 'Maximum detail',
        'resolution_cm': 1,
        'reduce_images': False,
        'description': 'Slowest option for final orthophotos on capable hardware.',
    },
]


def _render_new_run_page(
    request: Request,
    *,
    upload_run_id: str | None = None,
    validation_result: dict[str, object] | None = None,
    form_values: dict[str, object] | None = None,
) -> HTMLResponse:
    orthophoto_runs: list[dict[str, object]] = []
    odm_runs_by_upload: dict[str, list[object]] = {}
    for run in deps.run_service.list_runs():
        upload_id = Path(run.input_path).name
        if not run.selected_steps.run_odm or run.status != 'completed':
            continue
        orthophoto_paths = {
            key: value
            for key, value in run.outputs.items()
            if key in {'orthophoto_rgb', 'orthophoto_mapir'} and value and Path(value).exists()
        }
        if not orthophoto_paths:
            continue
        odm_runs_by_upload.setdefault(upload_id, []).append(run)
        orthophoto_runs.append(
            {
                'run_id': run.run_id,
                'upload_run_id': upload_id,
                'dataset_name': run.dataset_name,
                'run_name': run.run_name,
                'created_at': run.created_at,
                'mapir_ready': 'orthophoto_mapir' in orthophoto_paths,
                'rgb_ready': 'orthophoto_rgb' in orthophoto_paths,
                'preset': run.parameters.get('orthophoto_preset') or '-',
                'resolution_cm': run.parameters.get('orthophoto_resolution_cm') or '-',
            }
        )

    uploads: list[dict[str, object]] = []
    for path in sorted(deps.storage_service.layout.uploads_root.iterdir(), reverse=True):
        if not path.is_dir():
            continue
        manifest = deps.storage_service.read_json(path / 'manifest.json', default={})
        odm_runs = odm_runs_by_upload.get(path.name, [])
        uploads.append(
            {
                'run_id': path.name,
                'dataset_name': manifest.get('dataset_name') or path.name,
                'mapir_count': len(manifest.get('mapir_files', [])),
                'rgb_count': len(manifest.get('rgb_files', [])),
                'orthophoto_ready': bool(odm_runs),
                'orthophoto_run_id': getattr(odm_runs[0], 'run_id', None) if odm_runs else None,
                'selected': path.name == upload_run_id,
            }
        )
    orthophoto_uploads = orthophoto_runs
    model_catalog = list(PDM_MODEL_CATALOG)
    models_by_crop = {}
    for item in model_catalog:
        models_by_crop.setdefault(item['crop'], []).append(item)
    settings_view = deps.settings_service.get_settings_view()
    return deps.templates.TemplateResponse(
        request,
        'new_run.html',
        {
            'uploads': uploads,
            'orthophoto_uploads': orthophoto_uploads,
            'orthophoto_runs': orthophoto_runs,
            'orthophoto_presets': ORTHOPHOTO_PRESETS,
            'selected_upload_run_id': upload_run_id,
            'validation_result': validation_result,
            'form_values': form_values or {},
            'pdm_model_catalog': model_catalog,
            'pdm_models_by_crop': models_by_crop,
            'pdm_default_crop': settings_view['non_secret'].get('pdm_default_crop', 'grapevine'),
            'pdm_default_model_key': settings_view['non_secret'].get('pdm_default_model_key', 'grapevine_powdery_mildew_risk_v1'),
            'pdm_enabled_by_default': settings_view['non_secret'].get('pdm_enabled_by_default', True),
        },
    )


def _run_mode_label(run) -> str:
    return 'Full ODM' if run.selected_steps.run_odm else 'Existing orthos'


def _filter_runs(runs, status: str | None = None, query: str | None = None, run_mode: str | None = None):
    filtered = list(runs)
    if status and status != 'all':
        filtered = [run for run in filtered if run.status == status]
    if run_mode and run_mode != 'all':
        wants_odm = run_mode == 'full_odm'
        filtered = [run for run in filtered if run.selected_steps.run_odm is wants_odm]
    if query:
        normalized = query.strip().lower()
        if normalized:
            filtered = [
                run
                for run in filtered
                if normalized in run.run_id.lower()
                or normalized in (run.run_name or '').lower()
                or normalized in run.dataset_name.lower()
                or normalized in (run.stage_message or '').lower()
            ]
    return filtered


@router.get('/runs/new', response_class=HTMLResponse)
def new_run_page(request: Request, upload_run_id: str | None = None) -> HTMLResponse:
    return _render_new_run_page(request, upload_run_id=upload_run_id)


@router.get('/runs')
def list_runs(request: Request, status: str = 'all', q: str = '', run_mode: str = 'all'):
    runs = deps.run_service.list_runs()
    filtered_runs = _filter_runs(runs, status=status, query=q, run_mode=run_mode)
    if 'text/html' in request.headers.get('accept', ''):
        return deps.templates.TemplateResponse(
            request,
            'runs.html',
            {
                'runs': filtered_runs,
                'total_runs': len(runs),
                'filtered_count': len(filtered_runs),
                'status_filter': status,
                'query': q,
                'run_mode_filter': run_mode,
                'run_mode_label': _run_mode_label,
            },
        )
    return [item.model_dump(mode='json') for item in filtered_runs]


@router.get('/runs/{run_id}')
def get_run(run_id: str, request: Request):
    try:
        run = deps.run_service.load_run(run_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail='Run not found.') from exc
    report = deps.report_service.get_report(run_id)
    payload = run.model_dump(mode='json')
    payload['logs'] = deps.run_service.log_text(run_id)
    payload['report'] = report.model_dump(mode='json')
    if request is not None and 'text/html' in request.headers.get('accept', ''):
        return deps.templates.TemplateResponse(
            request,
            'run_detail.html',
            {'run': run, 'report': report, 'logs': payload['logs']},
        )
    return payload


@router.post('/runs')
def create_run(request: RunCreateRequest) -> dict[str, str]:
    record = deps.run_service.create_run_record(request)
    result = deps.run_service.start_run(record.run_id)
    return {'run_id': result.run_id, 'status': result.status, 'redirect': f'/runs/{result.run_id}'}


@router.post('/runs/validate')
def validate_run(request: RunCreateRequest) -> dict[str, object]:
    return deps.preflight_service.validate(request)


@router.get('/runs/{run_id}/status')
def get_run_status(run_id: str) -> dict:
    run = deps.run_service.load_run(run_id)
    payload = run.model_dump(mode='json')
    payload['logs'] = deps.run_service.log_text(run_id)
    payload['report'] = deps.report_service.get_report(run_id).model_dump(mode='json')
    return payload


@router.post('/runs/{run_id}/stop')
def stop_run(run_id: str) -> dict:
    try:
        run = deps.run_service.request_stop(run_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail='Run not found.') from exc
    return run.model_dump(mode='json')


@router.post('/ui/runs')
def create_run_ui(
    request: Request,
    source_orthophoto_run_id: str = Form(...),
    run_name: str = Form(''),
    fetch_weather: bool = Form(False),
    run_irrigation: bool = Form(False),
    run_pdm: bool = Form(False),
    pdm_crop: str = Form('grapevine'),
    pdm_model_key: str = Form('grapevine_powdery_mildew_risk_v1'),
    generate_report: bool = Form(False),
):
    source_run = deps.run_service.load_run(source_orthophoto_run_id)
    upload_run_id = Path(source_run.input_path).name
    manifest = deps.storage_service.read_json(deps.storage_service.upload_dir(upload_run_id) / 'manifest.json')
    dataset_name = str(manifest.get('dataset_name') or upload_run_id)
    normalized_run_name = run_name.strip() if run_name.strip() else None
    run_request = RunCreateRequest.model_validate(
        {
            'run_name': normalized_run_name,
            'dataset_name': dataset_name,
            'upload_run_id': upload_run_id,
            'selected_steps': {
                'resize_images': False,
                'run_odm': False,
                'fetch_weather': fetch_weather,
                'run_irrigation': run_irrigation,
                'run_pdm': run_pdm,
                'generate_report': generate_report,
            },
            'parameters': {
                'source_orthophoto_run_id': source_orthophoto_run_id,
                'pdm_crop': pdm_crop,
                'pdm_model_key': pdm_model_key,
            },
        }
    )
    validation = deps.preflight_service.validate(run_request)
    if not validation.get('ok'):
        return _render_new_run_page(
            request,
            upload_run_id=upload_run_id,
            validation_result=validation,
            form_values={
                'run_name': run_name,
                'fetch_weather': fetch_weather,
                'run_irrigation': run_irrigation,
                'run_pdm': run_pdm,
                'pdm_crop': pdm_crop,
                'pdm_model_key': pdm_model_key,
                'generate_report': generate_report,
            },
        )
    created = create_run(run_request)
    return RedirectResponse(url=created['redirect'], status_code=303)


@router.post('/ui/runs/{run_id}/stop')
def stop_run_ui(run_id: str) -> RedirectResponse:
    stop_run(run_id)
    return RedirectResponse(url=f'/runs/{run_id}', status_code=303)


@router.post('/ui/runs/{run_id}/delete')
def delete_run_ui(run_id: str) -> RedirectResponse:
    try:
        deps.run_service.delete_run(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail='Run not found.') from exc
    return RedirectResponse(url='/runs', status_code=303)


@router.post('/ui/runs/{run_id}/archive')
def archive_run_ui(run_id: str) -> RedirectResponse:
    try:
        deps.run_service.archive_run(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail='Run not found.') from exc
    return RedirectResponse(url='/runs', status_code=303)


@router.post('/ui/orthophotos/{run_id}/delete')
def delete_orthophoto_ui(run_id: str) -> RedirectResponse:
    try:
        deps.run_service.delete_run(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail='Orthophoto set not found.') from exc
    return RedirectResponse(url='/runs/new', status_code=303)


@router.post('/ui/runs/clear-stuck')
def clear_stuck_runs_ui() -> RedirectResponse:
    deps.run_service.clear_stuck_active_runs()
    return RedirectResponse(url='/runs?status=cancelled', status_code=303)


@router.post('/ui/runs/clear-incomplete')
def clear_incomplete_runs_ui() -> RedirectResponse:
    deps.run_service.clear_incomplete_runs()
    return RedirectResponse(url='/runs', status_code=303)
