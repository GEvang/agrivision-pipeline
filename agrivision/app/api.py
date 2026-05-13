from __future__ import annotations

import subprocess
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request as UrlRequest, urlopen

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from PIL import Image, UnidentifiedImageError

from agrivision.app.commands.doctor import doctor
from agrivision.app.schemas.runs import RunCreateRequest, UploadManifest
from agrivision.app.schemas.settings import (
    CredentialsUpdateRequest,
    SettingsUpdateRequest,
)
from agrivision.config import get_project_root, load_config
from agrivision.config.settings import load_local_env
from agrivision.services.report_service import ReportService
from agrivision.services.run_service import RunService
from agrivision.services.preflight_service import PreflightService
from agrivision.services.service_control import ensure_service, restart_service, service_statuses
from agrivision.services.settings_service import SettingsService
from agrivision.services.storage_service import StorageService
from agrivision.services.pdm.catalog import PDM_MODEL_CATALOG, get_models_for_crop

load_local_env()

app = FastAPI(title='AgriVision Dashboard', version='0.2.0')
app.mount('/static', StaticFiles(directory=str(Path(__file__).parent / 'web' / 'static')), name='static')
storage_service = StorageService()
run_service = RunService(storage_service)
report_service = ReportService(run_service=run_service)
preflight_service = PreflightService(storage_service)
settings_service = SettingsService()
TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / 'web' / 'templates'))



def _format_system_datetime(value):
    if value is None:
        return ''
    if isinstance(value, str):
        try:
            from datetime import datetime
            value = datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError:
            return value
    try:
        localized = value.astimezone() if getattr(value, 'tzinfo', None) is not None else value
    except Exception:
        localized = value
    return localized.strftime('%Y-%m-%d %H:%M:%S')


def _format_duration(started_at, finished_at):
    if started_at is None:
        return '-'
    end_value = finished_at
    if end_value is None:
        from datetime import datetime, timezone
        end_value = datetime.now(timezone.utc)
    try:
        seconds = int(max(0, (end_value - started_at).total_seconds()))
    except Exception:
        return '-'
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f'{hours}h {minutes}m'
    if minutes:
        return f'{minutes}m {secs}s'
    return f'{secs}s'


def _step_summary(run) -> str:
    selected = run.selected_steps
    parts = [
        'ODM' if selected.run_odm else 'Existing orthos',
        'Weather' if selected.fetch_weather else 'No weather',
        'PDM' if selected.run_pdm else 'No PDM',
    ]
    if selected.resize_images:
        parts.insert(0, 'Resize')
    return ' / '.join(parts)


def _url_health(name: str, base_url: str, paths: tuple[str, ...] = ('/health', '/docs', '/openapi.json')) -> dict[str, str]:
    for path in paths:
        url = base_url.rstrip('/') + path
        try:
            request = UrlRequest(url, method='GET')
            with urlopen(request, timeout=0.8) as response:
                if 200 <= response.status < 500:
                    state = 'ok' if response.status < 400 else 'warn'
                    return {'name': name, 'state': state, 'detail': f'HTTP {response.status}', 'target': url}
        except (OSError, URLError):
            continue
    return {'name': name, 'state': 'down', 'detail': 'Not reachable', 'target': base_url}


def _docker_health() -> dict[str, str]:
    try:
        result = subprocess.run(
            ['docker', 'version', '--format', '{{.Server.Version}}'],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return {'name': 'Docker', 'state': 'down', 'detail': 'Unavailable', 'target': 'docker'}
    version = result.stdout.strip()
    if result.returncode == 0 and version:
        return {'name': 'Docker', 'state': 'ok', 'detail': version, 'target': 'docker'}
    return {'name': 'Docker', 'state': 'warn', 'detail': 'Installed, daemon unavailable', 'target': 'docker'}


def _service_health() -> list[dict[str, str]]:
    config = load_config()
    return [
        _docker_health(),
        _url_health('Weather', config.get('weather', {}).get('base_url', '')),
        _url_health('Irrigation', config.get('irrigation', {}).get('base_url', '')),
        _url_health('PDM', config.get('pdm', {}).get('base_url', '')),
    ]


TEMPLATES.env.filters['system_datetime'] = _format_system_datetime
TEMPLATES.env.filters['duration'] = _format_duration

ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.tif', '.tiff'}
MINIMUM_DATASET_IMAGES = 2


@app.get('/health')
def health() -> dict[str, str]:
    return {'status': 'ok'}


@app.get('/doctor')
def doctor_endpoint() -> dict[str, str]:
    return doctor()


@app.get('/', response_class=HTMLResponse)
def dashboard(request: Request) -> HTMLResponse:
    runs = run_service.list_runs()
    status_summary: dict[str, int] = {}
    for run in runs:
        status_summary[run.status] = status_summary.get(run.status, 0) + 1
    latest_report = report_service.latest_report(generate_preview=False)
    active_runs = sum(1 for run in runs if run.status in {'queued', 'running'})
    return TEMPLATES.TemplateResponse(
        request,
        'dashboard.html',
        {
            'recent_runs': runs[:10],
            'total_runs': len(runs),
            'active_runs': active_runs,
            'status_summary': status_summary,
            'latest_report': latest_report,
            'service_health': _service_health(),
            'step_summary': _step_summary,
        },
    )


@app.get('/runs/new', response_class=HTMLResponse)
def new_run_page(request: Request, upload_run_id: str | None = None) -> HTMLResponse:
    return _render_new_run_page(request, upload_run_id=upload_run_id)


def _render_new_run_page(
    request: Request,
    *,
    upload_run_id: str | None = None,
    validation_result: dict[str, object] | None = None,
    form_values: dict[str, object] | None = None,
) -> HTMLResponse:
    uploads: list[dict[str, object]] = []
    for path in sorted(storage_service.layout.uploads_root.iterdir(), reverse=True):
        if not path.is_dir():
            continue
        manifest = storage_service.read_json(path / 'manifest.json', default={})
        uploads.append(
            {
                'run_id': path.name,
                'dataset_name': manifest.get('dataset_name') or path.name,
                'mapir_count': len(manifest.get('mapir_files', [])),
                'rgb_count': len(manifest.get('rgb_files', [])),
                'selected': path.name == upload_run_id,
            }
        )
    model_catalog = list(PDM_MODEL_CATALOG)
    models_by_crop = {}
    for item in model_catalog:
        models_by_crop.setdefault(item['crop'], []).append(item)
    settings_view = settings_service.get_settings_view()
    return TEMPLATES.TemplateResponse(
        request,
        'new_run.html',
        {
            'uploads': uploads,
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


@app.get('/runs')
def list_runs(request: Request, status: str = 'all', q: str = '', run_mode: str = 'all'):
    runs = run_service.list_runs()
    filtered_runs = _filter_runs(runs, status=status, query=q, run_mode=run_mode)
    if 'text/html' in request.headers.get('accept', ''):
        return TEMPLATES.TemplateResponse(
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


@app.get('/runs/{run_id}')
def get_run(run_id: str, request: Request):
    try:
        run = run_service.load_run(run_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail='Run not found.') from exc
    report = report_service.get_report(run_id)
    payload = run.model_dump(mode='json')
    payload['logs'] = run_service.log_text(run_id)
    payload['report'] = report.model_dump(mode='json')
    if request is not None and 'text/html' in request.headers.get('accept', ''):
        return TEMPLATES.TemplateResponse(
            request,
            'run_detail.html',
            {'run': run, 'report': report, 'logs': payload['logs']},
        )
    return payload


@app.post('/runs')
def create_run(request: RunCreateRequest) -> dict[str, str]:
    record = run_service.create_run_record(request)
    result = run_service.start_run(record.run_id)
    return {'run_id': result.run_id, 'status': result.status, 'redirect': f'/runs/{result.run_id}'}


@app.post('/runs/validate')
def validate_run(request: RunCreateRequest) -> dict[str, object]:
    return preflight_service.validate(request)


@app.get('/runs/{run_id}/status')
def get_run_status(run_id: str) -> dict:
    run = run_service.load_run(run_id)
    payload = run.model_dump(mode='json')
    payload['logs'] = run_service.log_text(run_id)
    payload['report'] = report_service.get_report(run_id).model_dump(mode='json')
    return payload


@app.post('/runs/{run_id}/stop')
def stop_run(run_id: str) -> dict:
    try:
        run = run_service.request_stop(run_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail='Run not found.') from exc
    return run.model_dump(mode='json')


@app.post('/uploads/images')
async def upload_images(
    dataset_name: str = Form(...),
    mapir_files: list[UploadFile] = File(...),
    rgb_files: list[UploadFile] = File(...),
) -> dict[str, object]:
    upload_run_id = storage_service.new_run_id()
    upload_dir = storage_service.upload_dir(upload_run_id)
    mapir_dir = upload_dir / 'mapir'
    rgb_dir = upload_dir / 'rgb'
    mapir_dir.mkdir(parents=True, exist_ok=True)
    rgb_dir.mkdir(parents=True, exist_ok=True)

    async def _store_images(kind: str, uploads: list[UploadFile], target_dir: Path) -> tuple[list[str], list[str]]:
        seen_names: set[str] = set()
        stored_files: list[str] = []
        validation_errors: list[str] = []
        for upload in uploads:
            suffix = Path(upload.filename or '').suffix.lower()
            name = Path(upload.filename or '').name
            if suffix not in ALLOWED_EXTENSIONS:
                validation_errors.append(f'{kind} - {name}: unsupported file type')
                continue
            if not name or name in seen_names:
                validation_errors.append(f'{kind} - {name or "<unnamed>"}: duplicate or invalid name')
                continue
            seen_names.add(name)
            data = await upload.read()
            if not data:
                validation_errors.append(f'{kind} - {name}: empty file')
                continue
            target = target_dir / name
            target.write_bytes(data)
            try:
                with Image.open(target) as image:
                    image.verify()
            except (UnidentifiedImageError, OSError):
                target.unlink(missing_ok=True)
                validation_errors.append(f'{kind} - {name}: unreadable or corrupt image')
                continue
            stored_files.append(name)
        return stored_files, validation_errors

    mapir_stored_files, mapir_errors = await _store_images('MAPIR', mapir_files, mapir_dir)
    rgb_stored_files, rgb_errors = await _store_images('RGB', rgb_files, rgb_dir)
    errors = [*mapir_errors, *rgb_errors]

    if len(mapir_stored_files) < MINIMUM_DATASET_IMAGES:
        errors.append(f'MAPIR: at least {MINIMUM_DATASET_IMAGES} valid images are required.')
    if len(rgb_stored_files) < MINIMUM_DATASET_IMAGES:
        errors.append(f'RGB: at least {MINIMUM_DATASET_IMAGES} valid images are required.')
    if errors:
        raise HTTPException(status_code=400, detail=errors)

    manifest = UploadManifest(
        run_id=upload_run_id,
        dataset_name=dataset_name,
        upload_dir=str(upload_dir),
        files=sorted([f'mapir/{name}' for name in mapir_stored_files] + [f'rgb/{name}' for name in rgb_stored_files]),
        mapir_files=sorted(mapir_stored_files),
        rgb_files=sorted(rgb_stored_files),
        created_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc),
    )
    storage_service.write_json(upload_dir / 'manifest.json', manifest.model_dump(mode='json'))
    return manifest.model_dump(mode='json')


@app.get('/reports')
def reports(request: Request):
    report_items = report_service.list_reports(generate_previews=False)
    if 'text/html' in request.headers.get('accept', ''):
        return TEMPLATES.TemplateResponse(request, 'reports.html', {'reports': report_items})
    return [item.model_dump(mode='json') for item in report_items]


@app.get('/reports/{run_id}')
def get_report(run_id: str) -> dict:
    return report_service.get_report(run_id).model_dump(mode='json')


@app.get('/reports/{run_id}/view', response_class=HTMLResponse)
def report_view(run_id: str, request: Request, embedded: bool = False) -> HTMLResponse:
    report = report_service.get_report(run_id)
    if not report.report_path:
        raise HTTPException(status_code=404, detail='Report not found.')
    run = run_service.load_run(run_id)
    template_name = 'report_embed.html' if embedded else 'report_view.html'
    return TEMPLATES.TemplateResponse(
        request,
        template_name,
        {'run': run, 'report': report},
    )


@app.get('/settings')
def settings_page(request: Request):
    view = settings_service.get_settings_view()
    if 'text/html' in request.headers.get('accept', ''):
        return TEMPLATES.TemplateResponse(request, 'settings.html', view)
    return view


@app.get('/services', response_class=HTMLResponse)
def services_page(request: Request) -> HTMLResponse:
    return TEMPLATES.TemplateResponse(
        request,
        'services.html',
        {'services': service_statuses(include_logs=True), 'message': None},
    )


@app.get('/services/status')
def services_status() -> list[dict[str, object]]:
    return service_statuses(include_logs=False)


@app.post('/settings')
def update_settings(request: SettingsUpdateRequest) -> dict:
    return settings_service.update_non_secret_settings(request)


@app.post('/settings/credentials')
def update_credentials(request: CredentialsUpdateRequest) -> dict:
    return settings_service.update_credentials(request)




@app.post('/ui/settings')
def update_settings_ui(
    location_name: str = Form(''),
    location_lat: float | None = Form(None),
    location_lon: float | None = Form(None),
    weather_base_url: str = Form(''),
    irrigation_base_url: str = Form(''),
    pdm_base_url: str = Form(''),
    pdm_enabled_by_default: bool = Form(False),
    pdm_default_crop: str = Form('grapevine'),
    pdm_default_model_key: str = Form('grapevine_powdery_mildew_risk_v1'),
    resize_max_long_edge: int | None = Form(None),
    orthophoto_resolution_cm: int | None = Form(None),
) -> RedirectResponse:
    update_settings(
        SettingsUpdateRequest(
            location_name=location_name or None,
            location_lat=location_lat,
            location_lon=location_lon,
            weather_base_url=weather_base_url or None,
            irrigation_base_url=irrigation_base_url or None,
            pdm_base_url=pdm_base_url or None,
            pdm_enabled_by_default=pdm_enabled_by_default,
            pdm_default_crop=pdm_default_crop or None,
            pdm_default_model_key=pdm_default_model_key or None,
            resize_max_long_edge=resize_max_long_edge,
            orthophoto_resolution_cm=orthophoto_resolution_cm,
        )
    )
    return RedirectResponse(url='/settings', status_code=303)


@app.post('/ui/settings/credentials')
def update_credentials_ui(
    shared_username: str = Form(''),
    shared_password: str = Form(''),
    openweather_api_key: str = Form(''),
) -> RedirectResponse:
    update_credentials(
        CredentialsUpdateRequest(
            shared_username=shared_username or None,
            shared_password=shared_password or None,
            openweather_api_key=openweather_api_key or None,
        )
    )
    return RedirectResponse(url='/settings', status_code=303)


@app.post('/ui/services/{service_key}/start')
def start_service_ui(service_key: str) -> RedirectResponse:
    if service_key not in {'weather', 'irrigation', 'pdm'}:
        raise HTTPException(status_code=404, detail='Service not found.')
    try:
        ensure_service(service_key, timeout_seconds=90)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return RedirectResponse(url='/services', status_code=303)


@app.post('/ui/services/{service_key}/restart')
def restart_service_ui(service_key: str) -> RedirectResponse:
    if service_key not in {'weather', 'irrigation', 'pdm'}:
        raise HTTPException(status_code=404, detail='Service not found.')
    try:
        restart_service(service_key, timeout_seconds=90)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return RedirectResponse(url='/services', status_code=303)


@app.get('/artifacts/{run_id}/report-assets/{asset_path:path}')
def report_asset(run_id: str, asset_path: str) -> FileResponse:
    run_service.load_run(run_id)
    config = load_config()
    output_root = (get_project_root() / config['paths']['output_root']).resolve()
    candidate = (output_root / asset_path).resolve()
    try:
        candidate.relative_to(output_root)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail='Artifact not found.') from exc
    if not candidate.exists() or not candidate.is_file():
        raise HTTPException(status_code=404, detail='Artifact file missing.')
    return FileResponse(candidate)


@app.get('/artifacts/{run_id}/{artifact_name}')
def artifact(run_id: str, artifact_name: str):
    run = run_service.load_run(run_id)
    report = report_service.get_report(run_id)
    options = {
        'report': report.report_path,
        'orthophoto': report.orthophoto_path,
        'preview': report.preview_path,
        'log': run.logs_path,
    }
    path = options.get(artifact_name)
    if not path:
        raise HTTPException(status_code=404, detail='Artifact not found.')
    resolved = Path(path)
    if not resolved.exists():
        raise HTTPException(status_code=404, detail='Artifact file missing.')
    if artifact_name == 'report':
        html = resolved.read_text(encoding='utf-8')
        base_tag = f'<base href="/artifacts/{run_id}/report-assets/">'
        if '</head>' in html:
            html = html.replace('</head>', f'  {base_tag}\n</head>', 1)
        else:
            html = base_tag + html
        return HTMLResponse(content=html)
    return FileResponse(resolved)


@app.post('/ui/uploads')
async def upload_images_ui(
    dataset_name: str = Form(...),
    mapir_files: list[UploadFile] = File(...),
    rgb_files: list[UploadFile] = File(...),
) -> RedirectResponse:
    manifest = await upload_images(dataset_name=dataset_name, mapir_files=mapir_files, rgb_files=rgb_files)
    return RedirectResponse(url=f"/runs/new?upload_run_id={manifest['run_id']}", status_code=303)


@app.post('/ui/runs')
def create_run_ui(
    request: Request,
    upload_run_id: str = Form(...),
    run_name: str = Form(''),
    run_mode: str = Form('full_odm'),
    resize_images: bool = Form(False),
    run_odm: bool = Form(False),
    fetch_weather: bool = Form(False),
    run_pdm: bool = Form(False),
    pdm_crop: str = Form('grapevine'),
    pdm_model_key: str = Form('grapevine_powdery_mildew_risk_v1'),
    generate_report: bool = Form(False),
):
    manifest = storage_service.read_json(storage_service.upload_dir(upload_run_id) / 'manifest.json')
    dataset_name = str(manifest.get('dataset_name') or upload_run_id)
    normalized_run_name = run_name.strip() if run_name.strip() else None
    normalized_run_odm = run_mode != 'existing_orthos' and run_odm
    run_request = RunCreateRequest.model_validate(
        {
            'run_name': normalized_run_name,
            'dataset_name': dataset_name,
            'upload_run_id': upload_run_id,
            'selected_steps': {
                'resize_images': resize_images,
                'run_odm': normalized_run_odm,
                'fetch_weather': fetch_weather,
                'run_pdm': run_pdm,
                'generate_report': generate_report,
            },
            'parameters': {
                'pdm_crop': pdm_crop,
                'pdm_model_key': pdm_model_key,
            },
        }
    )
    validation = preflight_service.validate(run_request)
    if not validation.get('ok'):
        return _render_new_run_page(
            request,
            upload_run_id=upload_run_id,
            validation_result=validation,
            form_values={
                'run_name': run_name,
                'run_mode': run_mode,
                'resize_images': resize_images,
                'run_odm': normalized_run_odm,
                'fetch_weather': fetch_weather,
                'run_pdm': run_pdm,
                'pdm_crop': pdm_crop,
                'pdm_model_key': pdm_model_key,
                'generate_report': generate_report,
            },
        )
    created = create_run(run_request)
    return RedirectResponse(url=created['redirect'], status_code=303)


@app.post('/ui/runs/{run_id}/stop')
def stop_run_ui(run_id: str) -> RedirectResponse:
    stop_run(run_id)
    return RedirectResponse(url=f'/runs/{run_id}', status_code=303)


@app.post('/ui/runs/{run_id}/delete')
def delete_run_ui(run_id: str) -> RedirectResponse:
    try:
        run_service.delete_run(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail='Run not found.') from exc
    return RedirectResponse(url='/runs', status_code=303)


@app.post('/ui/runs/{run_id}/archive')
def archive_run_ui(run_id: str) -> RedirectResponse:
    try:
        run_service.archive_run(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail='Run not found.') from exc
    return RedirectResponse(url='/runs', status_code=303)


@app.post('/ui/runs/clear-stuck')
def clear_stuck_runs_ui() -> RedirectResponse:
    run_service.clear_stuck_active_runs()
    return RedirectResponse(url='/runs?status=cancelled', status_code=303)
