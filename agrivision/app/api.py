from __future__ import annotations

from pathlib import Path

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
from agrivision.services.report_service import ReportService
from agrivision.services.run_service import RunService
from agrivision.services.settings_service import SettingsService
from agrivision.services.storage_service import StorageService

app = FastAPI(title='AgriVision Dashboard', version='0.2.0')
app.mount('/static', StaticFiles(directory=str(Path(__file__).parent / 'web' / 'static')), name='static')
storage_service = StorageService()
run_service = RunService(storage_service)
report_service = ReportService(run_service=run_service)
settings_service = SettingsService()
TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / 'web' / 'templates'))

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
    latest_report = report_service.list_reports()[0] if runs else None
    return TEMPLATES.TemplateResponse(
        request,
        'dashboard.html',
        {
            'recent_runs': runs[:10],
            'status_summary': status_summary,
            'latest_report': latest_report,
        },
    )


@app.get('/runs/new', response_class=HTMLResponse)
def new_run_page(request: Request, upload_run_id: str | None = None) -> HTMLResponse:
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
    return TEMPLATES.TemplateResponse(
        request,
        'new_run.html',
        {
            'uploads': uploads,
            'selected_upload_run_id': upload_run_id,
        },
    )


@app.get('/runs')
def list_runs() -> list[dict]:
    return [item.model_dump(mode='json') for item in run_service.list_runs()]


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


@app.get('/runs/{run_id}/status')
def get_run_status(run_id: str) -> dict:
    run = run_service.load_run(run_id)
    payload = run.model_dump(mode='json')
    payload['logs'] = run_service.log_text(run_id)
    payload['report'] = report_service.get_report(run_id).model_dump(mode='json')
    return payload


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
    report_items = report_service.list_reports()
    if 'text/html' in request.headers.get('accept', ''):
        return TEMPLATES.TemplateResponse(request, 'reports.html', {'reports': report_items})
    return [item.model_dump(mode='json') for item in report_items]


@app.get('/reports/{run_id}')
def get_report(run_id: str) -> dict:
    return report_service.get_report(run_id).model_dump(mode='json')


@app.get('/settings')
def settings_page(request: Request):
    view = settings_service.get_settings_view()
    if 'text/html' in request.headers.get('accept', ''):
        return TEMPLATES.TemplateResponse(request, 'settings.html', view)
    return view


@app.post('/settings')
def update_settings(request: SettingsUpdateRequest) -> dict:
    return settings_service.update_non_secret_settings(request)


@app.post('/settings/credentials')
def update_credentials(request: CredentialsUpdateRequest) -> dict:
    return settings_service.update_credentials(request)




@app.post('/ui/settings')
def update_settings_ui(
    location_name: str = Form(''),
    weather_base_url: str = Form(''),
    irrigation_base_url: str = Form(''),
    resize_max_long_edge: int | None = Form(None),
    orthophoto_resolution_cm: int | None = Form(None),
) -> RedirectResponse:
    update_settings(
        SettingsUpdateRequest(
            location_name=location_name or None,
            weather_base_url=weather_base_url or None,
            irrigation_base_url=irrigation_base_url or None,
            resize_max_long_edge=resize_max_long_edge,
            orthophoto_resolution_cm=orthophoto_resolution_cm,
        )
    )
    return RedirectResponse(url='/settings', status_code=303)


@app.post('/ui/settings/credentials')
def update_credentials_ui(
    weather_username: str = Form(''),
    weather_password: str = Form(''),
    openweather_api_key: str = Form(''),
    irrigation_email: str = Form(''),
    irrigation_password: str = Form(''),
    irrigation_token: str = Form(''),
) -> RedirectResponse:
    update_credentials(
        CredentialsUpdateRequest(
            weather_username=weather_username or None,
            weather_password=weather_password or None,
            openweather_api_key=openweather_api_key or None,
            irrigation_email=irrigation_email or None,
            irrigation_password=irrigation_password or None,
            irrigation_token=irrigation_token or None,
        )
    )
    return RedirectResponse(url='/settings', status_code=303)


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
    upload_run_id: str = Form(...),
    run_name: str = Form(''),
    resize_images: bool = Form(False),
    run_odm: bool = Form(False),
    fetch_weather: bool = Form(False),
    generate_report: bool = Form(False),
) -> RedirectResponse:
    manifest = storage_service.read_json(storage_service.upload_dir(upload_run_id) / 'manifest.json')
    dataset_name = str(manifest.get('dataset_name') or upload_run_id)
    normalized_run_name = run_name.strip() if run_name.strip() else dataset_name
    request = RunCreateRequest.model_validate(
        {
            'run_name': normalized_run_name,
            'dataset_name': dataset_name,
            'upload_run_id': upload_run_id,
            'selected_steps': {
                'resize_images': resize_images,
                'run_odm': run_odm,
                'fetch_weather': fetch_weather,
                'generate_report': generate_report,
            },
            'parameters': {},
        }
    )
    created = create_run(request)
    return RedirectResponse(url=created['redirect'], status_code=303)
