from __future__ import annotations

import io
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from agrivision.app import api
from agrivision.services.report_service import ReportService
from agrivision.services.run_service import RunService
from agrivision.services.settings_service import SettingsService
from agrivision.services.storage_service import StorageService


def _image_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new('RGB', (24, 24), color='white').save(buf, format='PNG')
    return buf.getvalue()


def test_api_create_run_upload_reports_and_settings(tmp_path: Path, monkeypatch) -> None:
    storage = StorageService(project_root=tmp_path)
    run_service = RunService(storage)
    report_service = ReportService(run_service=run_service)
    config_path = tmp_path / 'config.yaml'
    config_path.write_text('weather:\n  base_url: http://example\n', encoding='utf-8')
    settings_service = SettingsService(config_path=config_path, env_path=tmp_path / '.env')

    monkeypatch.setattr(api, 'storage_service', storage)
    monkeypatch.setattr(api, 'run_service', run_service)
    monkeypatch.setattr(api, 'report_service', report_service)
    monkeypatch.setattr(api, 'settings_service', settings_service)

    def fake_launch(run_id: str):
        report_path = tmp_path / 'output' / 'report' / 'index.html'
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text('<html>ok</html>', encoding='utf-8')
        ortho = tmp_path / 'ortho.tif'
        Image.new('RGB', (30, 30)).save(ortho)
        return run_service.update_status(run_id, status='completed', outputs={'report_html': str(report_path), 'orthophoto_rgb': str(ortho)})

    monkeypatch.setattr(run_service, 'start_run', fake_launch)

    client = TestClient(api.app)
    files = [
        ('mapir_files', ('mapir-a.png', _image_bytes(), 'image/png')),
        ('mapir_files', ('mapir-b.png', _image_bytes(), 'image/png')),
        ('rgb_files', ('rgb-a.png', _image_bytes(), 'image/png')),
        ('rgb_files', ('rgb-b.png', _image_bytes(), 'image/png')),
    ]
    upload_response = client.post('/uploads/images', data={'dataset_name': 'Dataset API'}, files=files)
    assert upload_response.status_code == 200, upload_response.text
    upload_run_id = upload_response.json()['run_id']

    create_response = client.post(
        '/runs',
        json={
            'run_name': 'Run 1',
            'dataset_name': 'Dataset API',
            'upload_run_id': upload_run_id,
            'selected_steps': {
                'resize_images': False,
                'run_odm': True,
                'fetch_weather': True,
                'generate_report': True,
            },
            'parameters': {'preset': 'default'},
        },
    )
    assert create_response.status_code == 200, create_response.text
    run_id = create_response.json()['run_id']

    detail = client.get(f'/runs/{run_id}', headers={'accept': 'application/json'})
    assert detail.status_code == 200
    assert detail.json()['status'] == 'completed'

    reports = client.get('/reports', headers={'accept': 'application/json'})
    assert reports.status_code == 200
    assert reports.json()[0]['run_id'] == run_id

    settings = client.post('/settings', json={'location_name': 'Farm X'})
    assert settings.status_code == 200
    assert settings.json()['non_secret']['location_name'] == 'Farm X'

    credentials = client.post('/settings/credentials', json={'weather_password': 'demo-pass'})
    assert credentials.status_code == 200
    assert credentials.json()['credentials']['weather_password'] != 'demo-pass'
