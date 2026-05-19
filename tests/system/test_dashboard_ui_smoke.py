from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from agrivision.app import api
from agrivision.app import dependencies as deps
from agrivision.app.routes import services as service_routes
from agrivision.app.routes import settings as settings_routes
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

    client = TestClient(api.app)
    dashboard = client.get('/', headers={'accept': 'text/html'})
    assert dashboard.status_code == 200
    assert 'Operations' not in dashboard.text
    new_run = client.get('/runs/new', headers={'accept': 'text/html'})
    assert new_run.status_code == 200
    assert 'Balanced (recommended)' in new_run.text
    assert 'Saved orthophotos' in new_run.text
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
