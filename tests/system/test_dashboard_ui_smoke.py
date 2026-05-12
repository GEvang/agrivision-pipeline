from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from agrivision.app import api
from agrivision.services.report_service import ReportService
from agrivision.services.run_service import RunService
from agrivision.services.settings_service import SettingsService
from agrivision.services.storage_service import StorageService


def test_dashboard_pages_render(tmp_path: Path, monkeypatch) -> None:
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

    run_dir = storage.run_dir('run-1')
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
        'outputs': {},
        'errors': [],
        'stages': [],
        'logs_path': str(run_dir / 'run.log'),
        'run_name': 'Smoke Run',
        'field_name': 'Field',
        'run_dir': str(run_dir),
    })
    (run_dir / 'run.log').write_text('ok', encoding='utf-8')

    client = TestClient(api.app)
    assert client.get('/', headers={'accept': 'text/html'}).status_code == 200
    assert client.get('/runs/new', headers={'accept': 'text/html'}).status_code == 200
    runs_page = client.get('/runs', headers={'accept': 'text/html'})
    assert runs_page.status_code == 200
    assert 'Run History' in runs_page.text
    assert client.get('/runs/run-1', headers={'accept': 'text/html'}).status_code == 200
    assert client.get('/settings', headers={'accept': 'text/html'}).status_code == 200
