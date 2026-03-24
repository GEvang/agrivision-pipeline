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
def new_run_page(request: Request) -> HTMLResponse:
    uploads = [p.name for p in sorted(storage_service.layout.uploads_root.iterdir(), reverse=True) if p.is_dir()]
    return TEMPLATES.TemplateResponse(request, 'new_run.html', {'uploads': uploads})


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
    result = run_service.launch_run(record.run_id)
    return {'run_id': result.run_id, 'status': result.status, 'redirect': f'/runs/{result.run_id}'}


@app.post('/uploads/images')
async def upload_images(dataset_name: str = Form(...), files: list[UploadFile] = File(...)) -> dict[str, object]:
    upload_run_id = storage_service.new_run_id()
    upload_dir = storage_service.upload_dir(upload_run_id)
    seen_names: set[str] = set()
    stored_files: list[str] = []
    errors: list[str] = []
    for upload in files:
        suffix = Path(upload.filename or '').suffix.lower()
        name = Path(upload.filename or '').name
        if suffix not in ALLOWED_EXTENSIONS:
            errors.append(f'{name}: unsupported file type')
            continue
        if not name or name in seen_names:
            errors.append(f'{name or "<unnamed>"}: duplicate or invalid name')
            continue
        seen_names.add(name)
        data = await upload.read()
        if not data:
            errors.append(f'{name}: empty file')
            continue
        target = upload_dir / name
        target.write_bytes(data)
        try:
            with Image.open(target) as image:
                image.verify()
        except (UnidentifiedImageError, OSError):
            target.unlink(missing_ok=True)
            errors.append(f'{name}: unreadable or corrupt image')
            continue
        stored_files.append(name)

    if len(stored_files) < MINIMUM_DATASET_IMAGES:
        errors.append(f'At least {MINIMUM_DATASET_IMAGES} valid images are required.')
    if errors:
        raise HTTPException(status_code=400, detail=errors)

    manifest = UploadManifest(
        run_id=upload_run_id,
        dataset_name=dataset_name,
        upload_dir=str(upload_dir),
        files=stored_files,
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


@app.get('/artifacts/{run_id}/{artifact_name}')
def artifact(run_id: str, artifact_name: str) -> FileResponse:
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
    return FileResponse(resolved)


@app.post('/ui/uploads')
async def upload_images_ui(dataset_name: str = Form(...), files: list[UploadFile] = File(...)) -> RedirectResponse:
    manifest = await upload_images(dataset_name=dataset_name, files=files)
    return RedirectResponse(url=f"/runs/new?upload_run_id={manifest['run_id']}", status_code=303)


@app.post('/ui/runs')
def create_run_ui(
    run_name: str = Form(...),
    dataset_name: str = Form(...),
    upload_run_id: str = Form(...),
    field_name: str = Form(''),
    preset: str = Form(''),
    notes: str = Form(''),
    flight_date: str = Form(''),
    resize_images: bool = Form(False),
    run_odm: bool = Form(False),
    generate_orthophoto: bool = Form(False),
    fetch_weather: bool = Form(False),
    generate_report: bool = Form(False),
) -> RedirectResponse:
    request = RunCreateRequest.model_validate(
        {
            'run_name': run_name,
            'dataset_name': dataset_name,
            'field_name': field_name or None,
            'upload_run_id': upload_run_id,
            'selected_steps': {
                'resize_images': resize_images,
                'run_odm': run_odm,
                'generate_orthophoto': generate_orthophoto,
                'fetch_weather': fetch_weather,
                'generate_report': generate_report,
            },
            'parameters': {
                'preset': preset or None,
                'notes': notes or None,
                'flight_date': flight_date or None,
            },
        }
    )
    created = create_run(request)
    return RedirectResponse(url=created['redirect'], status_code=303)
