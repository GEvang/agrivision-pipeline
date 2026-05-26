from __future__ import annotations

import time
from io import BytesIO
from pathlib import Path

import numpy as np
import rasterio
from fastapi.testclient import TestClient
from PIL import Image
from rasterio.transform import from_origin

from agrivision.app import api
from agrivision.app import dependencies as deps
from agrivision.app.routes import services as service_routes
from agrivision.app.routes import settings as settings_routes
from agrivision.services.report_service import ReportService
from agrivision.services.run_service import RunService
from agrivision.services.settings_service import SettingsService
from agrivision.services.storage_service import StorageService


def _wait_for_run(run_service: RunService, run_id: str, predicate, timeout: float = 3.0):
    deadline = time.monotonic() + timeout
    record = run_service.load_run(run_id)
    while time.monotonic() < deadline:
        record = run_service.load_run(run_id)
        if predicate(record):
            return record
        time.sleep(0.05)
    return record


def test_dashboard_pages_render(tmp_path: Path, monkeypatch) -> None:
    storage = StorageService(project_root=tmp_path)
    run_service = RunService(storage)
    report_service = ReportService(run_service=run_service)
    config_path = tmp_path / 'config.yaml'
    config_path.write_text('weather:\n  base_url: http://example\n', encoding='utf-8')
    settings_service = SettingsService(config_path=config_path, env_path=tmp_path / '.env')

    monkeypatch.setattr(deps, 'storage_service', storage)
    monkeypatch.setattr(deps, 'run_service', run_service)
    monkeypatch.setattr(deps, 'report_service', report_service)
    monkeypatch.setattr(deps, 'settings_service', settings_service)

    run_dir = storage.run_dir('run-1')
    report_path = run_dir / 'report.html'
    report_path.write_text('<html><body><h1>Field Analysis and Risk Mapping</h1></body></html>', encoding='utf-8')
    storage.write_json(run_dir / 'status.json', {
        'run_id': 'run-1',
        'created_at': '2026-03-24T10:00:00Z',
        'updated_at': '2026-03-24T10:00:00Z',
        'dataset_name': 'Smoke',
        'input_path': str(tmp_path / 'data' / 'uploads' / 'u1'),
        'status': 'completed',
        'progress_percent': 100,
        'current_stage': 'completed',
        'stage_message': 'Pipeline completed',
        'selected_steps': {'resize_images': False, 'run_odm': True, 'fetch_weather': True, 'generate_report': True},
        'started_at': '2026-03-24T10:00:05Z',
        'finished_at': '2026-03-24T10:05:05Z',
        'parameters': {},
        'outputs': {'report_html': str(report_path)},
        'errors': [],
        'stages': [],
        'logs_path': str(run_dir / 'run.log'),
        'run_name': 'Smoke Run',
        'field_name': 'Field',
        'run_dir': str(run_dir),
    })
    (run_dir / 'run.log').write_text('ok', encoding='utf-8')
    upload_dir = storage.upload_dir('ortho-upload')
    storage.write_json(upload_dir / 'manifest.json', {
        'run_id': 'ortho-upload',
        'dataset_name': 'Ortho Smoke',
        'upload_dir': str(upload_dir),
        'files': [],
        'rgb_files': [],
        'mapir_files': [],
        'thermal_files': [],
        'created_at': '2026-03-24T10:00:00Z',
    })
    ortho_dir = tmp_path / 'output' / 'runs' / 'ortho-run' / 'orthophotos'
    ortho_dir.mkdir(parents=True, exist_ok=True)
    ortho_path = ortho_dir / 'orthophoto_rgb.tif'
    ortho_path.write_bytes(b'placeholder')
    storage.write_json(storage.run_dir('ortho-run') / 'status.json', {
        'run_id': 'ortho-run',
        'created_at': '2026-03-24T11:00:00Z',
        'updated_at': '2026-03-24T11:00:00Z',
        'dataset_name': 'Ortho Smoke',
        'input_path': str(upload_dir),
        'status': 'completed',
        'progress_percent': 100,
        'current_stage': 'completed',
        'stage_message': 'Orthophoto completed',
        'selected_steps': {
            'resize_images': False,
            'run_odm': True,
            'fetch_weather': False,
            'run_irrigation': False,
            'run_pdm': False,
            'generate_report': False,
        },
        'started_at': '2026-03-24T11:00:05Z',
        'finished_at': '2026-03-24T11:05:05Z',
        'parameters': {'orthophoto_preset': 'balanced', 'orthophoto_resolution_cm': 3, 'camera_targets': ['rgb']},
        'outputs': {'orthophoto_rgb': str(ortho_path)},
        'errors': [],
        'stages': [],
        'logs_path': str(storage.run_dir('ortho-run') / 'run.log'),
        'run_name': 'Ortho Smoke orthophotos',
        'field_name': None,
        'run_dir': str(storage.run_dir('ortho-run')),
    })
    (storage.run_dir('ortho-run') / 'run.log').write_text('ok', encoding='utf-8')

    client = TestClient(api.app)
    dashboard = client.get('/', headers={'accept': 'text/html'})
    assert dashboard.status_code == 200
    assert 'Operations' not in dashboard.text
    new_run = client.get('/runs/new', headers={'accept': 'text/html'})
    assert new_run.status_code == 200
    assert 'Orthophoto Intake' in new_run.text
    assert 'Save / Generate Orthophotos' in new_run.text
    assert 'Balanced (recommended)' in new_run.text
    assert 'Orthophoto Library' in new_run.text
    assert 'Complete Orthophoto' not in new_run.text
    assert 'complete_run_id=' in new_run.text
    assert 'camera_kind=mapir' in new_run.text
    complete_page = client.get('/runs/new?complete_run_id=ortho-run&camera_kind=mapir', headers={'accept': 'text/html'})
    assert complete_page.status_code == 200
    assert 'Complete dataset' in complete_page.text
    assert 'Orthophoto Creation' not in complete_page.text
    assert 'Perform Parcel Analysis' not in complete_page.text
    assert 'Missing orthophotos' in complete_page.text
    assert 'Process Missing Orthophotos' in complete_page.text
    assert 'MAPIR drone images' in complete_page.text
    assert 'THERMAL drone images' in complete_page.text
    assert 'Build from images' in complete_page.text
    assert 'Use ready orthophoto' in complete_page.text
    runs_page = client.get('/runs', headers={'accept': 'text/html'})
    assert runs_page.status_code == 200
    assert 'Reports' in runs_page.text
    assert 'Clear incomplete' in runs_page.text
    run_detail = client.get('/runs/run-1', headers={'accept': 'text/html'})
    assert run_detail.status_code == 200
    assert 'Result Quality' not in run_detail.text
    report_view_template = Path('agrivision/app/web/templates/report_view.html').read_text(encoding='utf-8')
    assert 'Result Quality' not in report_view_template
    assert 'run-meta-grid' not in report_view_template
    monkeypatch.setattr(service_routes, 'service_statuses', lambda include_logs=False: [])
    monkeypatch.setattr(settings_routes, 'service_statuses', lambda include_logs=False: [])
    monkeypatch.setattr(settings_routes, 'docker_health', lambda: {'name': 'Docker', 'state': 'ok', 'detail': '27.0.0', 'target': 'docker'})
    monkeypatch.setattr(settings_routes, '_free_disk_gb', lambda: 120.0)
    monkeypatch.setattr(settings_routes, '_git_commit', lambda: 'abc1234')
    assert client.get('/services', headers={'accept': 'text/html'}, follow_redirects=False).status_code == 303
    settings_page = client.get('/settings', headers={'accept': 'text/html'})
    assert settings_page.status_code == 200
    assert 'Deployment' in settings_page.text
    assert 'Host readiness' in settings_page.text
    assert 'Cloudflare Tunnel checklist' in settings_page.text
    assert 'Cloudflare setup helper' in settings_page.text
    assert 'Cloudflare Access or equivalent external login is enabled' in settings_page.text
    assert 'Save deployment settings' in settings_page.text


def test_merged_orthophoto_form_imports_ready_geotiff(tmp_path: Path, monkeypatch) -> None:
    storage = StorageService(project_root=tmp_path)
    run_service = RunService(storage)
    monkeypatch.setattr(deps, 'storage_service', storage)
    monkeypatch.setattr(deps, 'run_service', run_service)

    geotiff = tmp_path / 'rgb.tif'
    with rasterio.open(
        geotiff,
        'w',
        driver='GTiff',
        width=2,
        height=2,
        count=1,
        dtype='uint8',
        crs='EPSG:4326',
        transform=from_origin(23.7, 38.0, 0.0001, 0.0001),
    ) as dataset:
        dataset.write(np.ones((1, 2, 2), dtype='uint8'))

    client = TestClient(api.app)
    with geotiff.open('rb') as handle:
        response = client.post(
            '/ui/orthophotos',
            data={
                'dataset_name': 'Merged Import',
                'rgb_source': 'ortho',
                'mapir_source': 'raw',
                'thermal_source': 'raw',
                'orthophoto_preset': 'balanced',
            },
            files={'rgb_orthophoto': ('rgb.tif', handle, 'image/tiff')},
            follow_redirects=False,
        )

    assert response.status_code == 303
    run_id = response.headers['location'].rsplit('/', 1)[-1]
    record = _wait_for_run(run_service, run_id, lambda item: item.status == 'completed')
    assert record.status == 'completed'
    assert Path(record.outputs['orthophoto_rgb']).exists()


def test_orthophoto_form_allows_rgb_only_with_empty_other_inputs(tmp_path: Path, monkeypatch) -> None:
    storage = StorageService(project_root=tmp_path)
    run_service = RunService(storage)
    monkeypatch.setattr(deps, 'storage_service', storage)
    monkeypatch.setattr(deps, 'run_service', run_service)
    monkeypatch.setattr(run_service, 'start_run', lambda run_id: run_service.load_run(run_id))

    def jpg_bytes(color: tuple[int, int, int]) -> bytes:
        buffer = BytesIO()
        Image.new('RGB', (8, 8), color).save(buffer, format='JPEG')
        return buffer.getvalue()

    client = TestClient(api.app)
    response = client.post(
        '/ui/orthophotos',
        data={
            'dataset_name': 'RGB Only',
            'rgb_source': 'raw',
            'mapir_source': 'raw',
            'thermal_source': 'raw',
            'orthophoto_preset': 'balanced',
        },
        files=[
            ('rgb_files', ('rgb-1.jpg', jpg_bytes((255, 0, 0)), 'image/jpeg')),
            ('rgb_files', ('rgb-2.jpg', jpg_bytes((0, 255, 0)), 'image/jpeg')),
        ],
        follow_redirects=False,
    )

    assert response.status_code == 303
    run_id = response.headers['location'].rsplit('/', 1)[-1]
    record = _wait_for_run(run_service, run_id, lambda item: item.current_stage != 'upload_validate')
    assert record.parameters['camera_targets'] == ['rgb']
    assert record.errors == []
