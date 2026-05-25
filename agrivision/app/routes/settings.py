from __future__ import annotations

import shutil
import subprocess
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import Request as UrlRequest
from urllib.request import urlopen

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from agrivision.app import dependencies as deps
from agrivision.app.health import docker_health
from agrivision.app.schemas.settings import (
    CredentialsUpdateRequest,
    SettingsUpdateRequest,
)
from agrivision.config import get_project_root, load_config
from agrivision.services.service_control import service_statuses

router = APIRouter()


@router.get('/settings')
def settings_page(request: Request):
    view = deps.settings_service.get_settings_view()
    view['services'] = service_statuses(include_logs=True)
    view['deployment_status'] = deployment_status()
    if 'text/html' in request.headers.get('accept', ''):
        return deps.templates.TemplateResponse(request, 'settings.html', view)
    return view


def deployment_status() -> dict[str, object]:
    config = load_config()
    app_cfg = config.get('app', {}) if isinstance(config.get('app'), dict) else {}
    deployment_mode = str(app_cfg.get('deployment_mode') or 'local')
    public_url = str(app_cfg.get('public_url') or '').rstrip('/')
    access_confirmed = _as_bool(app_cfg.get('external_access_protection_confirmed'), False)
    min_free_gb = _as_int(app_cfg.get('min_free_disk_gb'), 50)
    max_active_odm = max(1, _as_int(app_cfg.get('max_active_odm_runs'), 1))
    active_odm_runs = [
        run.run_id
        for run in deps.run_service.list_runs()
        if run.selected_steps.run_odm and run.status in {'queued', 'running'}
    ]
    free_gb = _free_disk_gb()
    docker = docker_health()
    disk_state = _disk_state(free_gb, min_free_gb)
    overall_state = 'ok'
    if docker['state'] == 'down' or disk_state == 'down' or len(active_odm_runs) >= max_active_odm:
        overall_state = 'warn'
    cloudflare_checks = _cloudflare_checks(deployment_mode, public_url, access_confirmed)
    if any(item['state'] == 'down' for item in cloudflare_checks):
        overall_state = 'warn'
    return {
        'state': overall_state,
        'deployment_mode': deployment_mode,
        'public_url': public_url,
        'external_access_protection_confirmed': access_confirmed,
        'free_disk_gb': free_gb,
        'min_free_disk_gb': min_free_gb,
        'disk_state': disk_state,
        'docker': docker,
        'active_odm_count': len(active_odm_runs),
        'active_odm_runs': active_odm_runs,
        'max_active_odm_runs': max_active_odm,
        'git_commit': _git_commit(),
        'cloudflare_checks': cloudflare_checks,
        'cloudflare_setup': _cloudflare_setup(public_url),
    }


def _cloudflare_checks(deployment_mode: str, public_url: str, access_confirmed: bool) -> list[dict[str, str]]:
    public_mode = deployment_mode in {'self_hosted', 'cloud'}
    checks = [
        {
            'name': 'Public deployment mode',
            'state': 'ok' if public_mode else 'warn',
            'detail': 'Self-hosted or cloud mode selected' if public_mode else 'Set mode to self-hosted or cloud before exposing the dashboard',
        },
        {
            'name': 'Public URL',
            'state': 'ok' if public_url else 'warn',
            'detail': public_url or 'Add the Cloudflare hostname for this dashboard',
        },
    ]
    if public_mode and public_url:
        checks.append(_public_health_check(public_url))
    elif not public_mode:
        checks.append(
            {
                'name': 'Tunnel reachability',
                'state': 'warn',
                'detail': 'Set mode to self-hosted or cloud before checking the tunnel',
            }
        )
    else:
        checks.append(
            {
                'name': 'Tunnel reachability',
                'state': 'warn',
                'detail': 'Waiting for a public URL',
            }
        )
    checks.append(
        {
            'name': 'Cloudflare Access',
            'state': 'ok' if access_confirmed else 'down',
            'detail': 'External access protection confirmed' if access_confirmed else 'Protect the tunnel with Cloudflare Access before sharing the URL',
        }
    )
    return checks


def _public_health_check(public_url: str) -> dict[str, str]:
    health_url = public_url.rstrip('/') + '/health'
    try:
        request = UrlRequest(health_url, method='GET')
        with urlopen(request, timeout=2.0) as response:
            if 200 <= response.status < 400:
                return {'name': 'Tunnel reachability', 'state': 'ok', 'detail': f'HTTP {response.status} at /health'}
            return {'name': 'Tunnel reachability', 'state': 'warn', 'detail': f'HTTP {response.status} at /health'}
    except (OSError, URLError):
        return {'name': 'Tunnel reachability', 'state': 'down', 'detail': f'Not reachable: {health_url}'}


def _cloudflare_setup(public_url: str) -> dict[str, object]:
    hostname = urlparse(public_url).hostname if public_url else ''
    local_service = 'http://localhost:8008'
    commands = [
        'cloudflared tunnel login',
        'cloudflared tunnel create agrivision',
    ]
    if hostname:
        commands.append(f'cloudflared tunnel route dns agrivision {hostname}')
    commands.extend(
        [
            'cloudflared tunnel run agrivision',
            'cloudflared service install',
        ]
    )
    config_lines = [
        'tunnel: agrivision',
        r'credentials-file: C:\Users\<user>\.cloudflared\<tunnel-id>.json',
        '',
        'ingress:',
    ]
    if hostname:
        config_lines.extend(
            [
                f'  - hostname: {hostname}',
                f'    service: {local_service}',
            ]
        )
    else:
        config_lines.extend(
            [
                '  - hostname: <your-hostname>',
                f'    service: {local_service}',
            ]
        )
    config_lines.append('  - service: http_status:404')
    return {
        'hostname': hostname,
        'local_service': local_service,
        'commands': commands,
        'config': '\n'.join(config_lines),
    }


def _free_disk_gb() -> float | None:
    try:
        usage = shutil.disk_usage(get_project_root())
    except OSError:
        return None
    return round(usage.free / (1024**3), 1)


def _disk_state(free_gb: float | None, min_free_gb: int) -> str:
    if free_gb is None:
        return 'warn'
    if free_gb < min_free_gb:
        return 'down'
    warn_threshold = max(min_free_gb * 1.5, min_free_gb + 20)
    if free_gb < warn_threshold:
        return 'warn'
    return 'ok'


def _git_commit() -> str:
    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--short', 'HEAD'],
            cwd=get_project_root(),
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return 'unknown'
    commit = result.stdout.strip()
    return commit if result.returncode == 0 and commit else 'unknown'


def _as_int(value: object, fallback: int) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return fallback


def _as_bool(value: object, fallback: bool) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return fallback
    normalized = str(value).strip().lower()
    if normalized in {'1', 'true', 'yes', 'on'}:
        return True
    if normalized in {'0', 'false', 'no', 'off'}:
        return False
    return fallback


@router.post('/settings')
def update_settings(request: SettingsUpdateRequest) -> dict:
    return deps.settings_service.update_non_secret_settings(request)


@router.post('/settings/credentials')
def update_credentials(request: CredentialsUpdateRequest) -> dict:
    return deps.settings_service.update_credentials(request)


@router.post('/ui/settings')
def update_settings_ui(
    location_name: str = Form(''),
    location_lat: float | None = Form(None),
    location_lon: float | None = Form(None),
    weather_base_url: str = Form(''),
    irrigation_base_url: str = Form(''),
    pdm_base_url: str = Form(''),
    pdm_enabled_by_default: bool | None = Form(None),
    pdm_default_crop: str | None = Form(None),
    pdm_default_model_key: str | None = Form(None),
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


@router.post('/ui/settings/deployment')
def update_deployment_settings_ui(
    deployment_mode: str = Form('local'),
    public_url: str = Form(''),
    min_free_disk_gb: int | None = Form(None),
    max_active_odm_runs: int | None = Form(None),
    external_access_protection_confirmed: bool = Form(False),
) -> RedirectResponse:
    update_settings(
        SettingsUpdateRequest(
            deployment_mode=deployment_mode,
            public_url=public_url or None,
            min_free_disk_gb=min_free_disk_gb,
            max_active_odm_runs=max_active_odm_runs,
            external_access_protection_confirmed=external_access_protection_confirmed,
        )
    )
    return RedirectResponse(url='/settings#deployment', status_code=303)


@router.post('/ui/settings/credentials')
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
