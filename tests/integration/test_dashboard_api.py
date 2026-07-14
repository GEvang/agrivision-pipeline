from __future__ import annotations

import io
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from agrivision.app import api
from agrivision.app import dependencies as deps
from agrivision.app.routes import uploads as upload_routes
from agrivision.app.schemas.runs import RunCreateRequest
from agrivision.services.report_service import ReportService
from agrivision.services.run_service import RunService, RunStartBlocked
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

    monkeypatch.setattr(deps, 'storage_service', storage)
    monkeypatch.setattr(deps, 'run_service', run_service)
    monkeypatch.setattr(deps, 'report_service', report_service)
    monkeypatch.setattr(deps, 'settings_service', settings_service)

    def fake_launch(run_id: str):
        report_path = tmp_path / 'output' / 'report' / 'index.html'
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            '<html><head></head><body><header class="report-appbar">old chrome</header>ok</body></html>',
            encoding='utf-8',
        )
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

    stop_completed = client.post(f'/runs/{run_id}/stop')
    assert stop_completed.status_code == 200
    assert stop_completed.json()['status'] == 'completed'

    reports = client.get('/reports', headers={'accept': 'application/json'})
    assert reports.status_code == 200
    assert reports.json()[0]['run_id'] == run_id

    embedded_report = client.get(f'/artifacts/{run_id}/report?embedded=true')
    assert embedded_report.status_code == 200
    assert '<body class="report-embedded">' in embedded_report.text
    assert 'old chrome' not in embedded_report.text

    printable_report = client.get(f'/artifacts/{run_id}/report')
    assert printable_report.status_code == 200
    assert '<body class="report-embedded">' not in printable_report.text
    assert 'old chrome' in printable_report.text

    settings = client.post('/settings', json={'location_name': 'Farm X'})
    assert settings.status_code == 200
    assert settings.json()['non_secret']['location_name'] == 'Farm X'

    credentials = client.post('/settings/credentials', json={'weather_password': 'demo-pass'})
    assert credentials.status_code == 200
    assert credentials.json()['credentials']['weather_password'] != 'demo-pass'


def test_report_artifacts_are_served_from_run_workspace(tmp_path: Path, monkeypatch) -> None:
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

    upload_dir = storage.upload_dir('upload-seed')
    (upload_dir / 'rgb').mkdir(parents=True, exist_ok=True)
    (upload_dir / 'mapir').mkdir(parents=True, exist_ok=True)
    record = run_service.create_run_record(
        RunCreateRequest.model_validate(
            {
                'run_name': 'Workspace Assets',
                'dataset_name': 'Dataset API',
                'upload_run_id': 'upload-seed',
                'selected_steps': {
                    'run_odm': True,
                    'fetch_weather': False,
                    'generate_report': True,
                },
                'parameters': {'preset': 'default'},
            }
        )
    )

    workspace = run_service.workspace_for_record(record)
    report_path = workspace.output_root / 'report' / 'index.html'
    report_path.parent.mkdir(parents=True, exist_ok=True)
    asset_path = workspace.output_root / 'report' / 'styles.css'
    asset_path.write_text('body { color: green; }', encoding='utf-8')
    report_path.write_text('<html><head></head><body><link rel="stylesheet" href="report/styles.css"></body></html>', encoding='utf-8')

    ortho = tmp_path / 'ortho.tif'
    Image.new('RGB', (30, 30)).save(ortho)
    run_service.update_status(
        record.run_id,
        status='completed',
        outputs={'report_html': str(report_path), 'orthophoto_rgb': str(ortho)},
    )

    client = TestClient(api.app)
    report_response = client.get(f'/artifacts/{record.run_id}/report')
    asset_response = client.get(f'/artifacts/{record.run_id}/report-assets/report/styles.css')
    traversal_response = client.get(f'/artifacts/{record.run_id}/report-assets/../status.json')

    assert report_response.status_code == 200
    assert '<base href="/artifacts/' in report_response.text
    assert asset_response.status_code == 200
    assert 'color: green' in asset_response.text
    assert traversal_response.status_code == 404


def test_api_create_run_returns_conflict_when_another_run_is_active(tmp_path: Path, monkeypatch) -> None:
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

    upload_dir = storage.upload_dir('upload-seed')
    (upload_dir / 'rgb').mkdir(parents=True, exist_ok=True)
    (upload_dir / 'mapir').mkdir(parents=True, exist_ok=True)
    storage.write_json(
        upload_dir / 'manifest.json',
        {
            'run_id': 'upload-seed',
            'dataset_name': 'Dataset API',
            'upload_dir': str(upload_dir),
            'files': ['rgb/a.png', 'rgb/b.png', 'mapir/a.png', 'mapir/b.png'],
            'rgb_files': ['a.png', 'b.png'],
            'mapir_files': ['a.png', 'b.png'],
            'created_at': '2026-06-22T00:00:00Z',
        },
    )

    def block_start(run_id: str):
        raise RunStartBlocked(
            'Another run is already active (active-run). Wait for it to finish or stop it before starting a new run.'
        )

    monkeypatch.setattr(run_service, 'start_run', block_start)

    client = TestClient(api.app)
    response = client.post(
        '/runs',
        json={
            'run_name': 'Blocked Run',
            'dataset_name': 'Dataset API',
            'upload_run_id': 'upload-seed',
            'selected_steps': {
                'run_odm': True,
                'fetch_weather': False,
                'generate_report': True,
            },
            'parameters': {'preset': 'default'},
        },
    )

    assert response.status_code == 409
    assert 'Another run is already active (active-run).' in response.json()['detail']


def test_dashboard_startup_reconciles_orphaned_active_runs(tmp_path: Path, monkeypatch) -> None:
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

    upload_dir = storage.upload_dir('upload-seed')
    (upload_dir / 'rgb').mkdir(parents=True, exist_ok=True)
    (upload_dir / 'mapir').mkdir(parents=True, exist_ok=True)

    queued = run_service.create_run_record(
        RunCreateRequest.model_validate(
            {
                'run_name': 'Queued Run',
                'dataset_name': 'Dataset API',
                'upload_run_id': 'upload-seed',
                'selected_steps': {
                    'run_odm': True,
                    'fetch_weather': False,
                    'generate_report': True,
                },
                'parameters': {'preset': 'default'},
            }
        )
    )
    running = run_service.create_run_record(
        RunCreateRequest.model_validate(
            {
                'run_name': 'Running Run',
                'dataset_name': 'Dataset API',
                'upload_run_id': 'upload-seed',
                'selected_steps': {
                    'run_odm': True,
                    'fetch_weather': False,
                    'generate_report': True,
                },
                'parameters': {'preset': 'default'},
            }
        )
    )
    run_service.update_status(running.run_id, status='running')
    run_service.update_stage(running.run_id, 'run_odm_rgb', 'running', 'Running ODM RGB')

    with TestClient(api.app) as client:
        response = client.get('/runs', headers={'accept': 'application/json'})
        assert response.status_code == 200

    queued_record = run_service.load_run(queued.run_id)
    running_record = run_service.load_run(running.run_id)

    for record in (queued_record, running_record):
        assert record.status == 'cancelled'
        assert record.finished_at is not None
        assert record.stage_message == RunService.RESTART_RECONCILIATION_MESSAGE
        assert record.errors == [RunService.RESTART_RECONCILIATION_MESSAGE]
        assert all(stage.state != 'running' for stage in record.stages)


def test_upload_rejects_duplicate_filenames_across_groups_and_cleans_up(tmp_path: Path, monkeypatch) -> None:
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

    client = TestClient(api.app)
    files = [
        ('mapir_files', ('shared.png', _image_bytes(), 'image/png')),
        ('mapir_files', ('mapir-b.png', _image_bytes(), 'image/png')),
        ('rgb_files', ('shared.png', _image_bytes(), 'image/png')),
        ('rgb_files', ('rgb-b.png', _image_bytes(), 'image/png')),
    ]

    response = client.post('/uploads/images', data={'dataset_name': 'Dataset API'}, files=files)

    assert response.status_code == 400
    assert any('duplicate or invalid name' in item for item in response.json()['detail'])
    assert list(storage.layout.uploads_root.glob('*')) == []


def test_upload_rejects_datasets_over_size_limit_and_cleans_up(tmp_path: Path, monkeypatch) -> None:
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
    monkeypatch.setattr(upload_routes, 'MAX_DATASET_BYTES', 32)

    client = TestClient(api.app)
    files = [
        ('mapir_files', ('mapir-a.png', _image_bytes(), 'image/png')),
        ('mapir_files', ('mapir-b.png', _image_bytes(), 'image/png')),
        ('rgb_files', ('rgb-a.png', _image_bytes(), 'image/png')),
        ('rgb_files', ('rgb-b.png', _image_bytes(), 'image/png')),
    ]

    response = client.post('/uploads/images', data={'dataset_name': 'Dataset API'}, files=files)

    assert response.status_code == 400
    assert any('dataset exceeds the 32 byte limit' in item for item in response.json()['detail'])
    assert list(storage.layout.uploads_root.glob('*')) == []


def test_upload_rejects_excess_files_per_group_and_cleans_up(tmp_path: Path, monkeypatch) -> None:
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
    monkeypatch.setattr(upload_routes, 'MAX_FILES_PER_GROUP', 1)

    client = TestClient(api.app)
    files = [
        ('mapir_files', ('mapir-a.png', _image_bytes(), 'image/png')),
        ('mapir_files', ('mapir-b.png', _image_bytes(), 'image/png')),
        ('rgb_files', ('rgb-a.png', _image_bytes(), 'image/png')),
        ('rgb_files', ('rgb-b.png', _image_bytes(), 'image/png')),
    ]

    response = client.post('/uploads/images', data={'dataset_name': 'Dataset API'}, files=files)

    assert response.status_code == 400
    assert any('no more than 1 files are allowed' in item for item in response.json()['detail'])
    assert list(storage.layout.uploads_root.glob('*')) == []


def test_pending_orthophoto_run_times_out_when_upload_never_arrives(tmp_path: Path, monkeypatch) -> None:
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
    monkeypatch.setattr(upload_routes.time, 'sleep', lambda _: None)

    client = TestClient(api.app)
    response = client.post(
        '/ui/orthophotos/init',
        json={
            'dataset_name': 'Dataset API',
            'orthophoto_preset': 'balanced',
            'raw_camera_targets': ['rgb'],
            'import_camera_targets': [],
        },
    )

    assert response.status_code == 200
    run_id = response.json()['run_id']

    upload_routes._expire_pending_upload_if_idle(run_id, timeout_seconds=1)
    record = run_service.load_run(run_id)

    assert record.status == 'failed'
    assert record.stage_message == 'Upload timed out before files reached the dashboard.'
    assert record.errors == ['Upload did not start within 1 seconds.']


def test_new_run_template_waits_for_upload_completion_before_redirect() -> None:
    template = Path('agrivision/app/web/templates/new_run.html').read_text(encoding='utf-8')

    assert "window.open('', '_blank')" not in template
    assert "window.location.href = uploadPayload?.redirect || initPayload.redirect;" in template


def test_runs_api_surfaces_corrupted_run_records(tmp_path: Path, monkeypatch) -> None:
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

    run_dir = storage.run_dir('broken-run')
    (run_dir / 'status.json').write_text('{"run_id":"broken-run"', encoding='utf-8')

    with TestClient(api.app) as client:
        response = client.get('/runs', headers={'accept': 'application/json'})
        detail = client.get('/runs/broken-run', headers={'accept': 'application/json'})

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]['run_id'] == 'broken-run'
    assert payload[0]['current_stage'] == 'corrupted'
    assert payload[0]['status'] == 'failed'
    assert detail.status_code == 200
    assert detail.json()['stage_message'] == RunService.CORRUPTED_RUN_MESSAGE
