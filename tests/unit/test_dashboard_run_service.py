from __future__ import annotations

from pathlib import Path

from agrivision.app.schemas.runs import RunCreateRequest
from agrivision.services.run_service import RunService
from agrivision.services.storage_service import StorageService


def _request(upload_run_id: str) -> RunCreateRequest:
    return RunCreateRequest.model_validate(
        {
            'run_name': 'Test Run',
            'dataset_name': 'Dataset 1',
            'field_name': 'Field 7',
            'upload_run_id': upload_run_id,
            'selected_steps': {
                'resize_images': True,
                'run_odm': True,
                'fetch_weather': False,
                'generate_report': True,
            },
            'parameters': {'preset': 'default', 'notes': 'ok'},
        }
    )


def test_run_record_creation_and_status_update(tmp_path: Path) -> None:
    storage = StorageService(project_root=tmp_path)
    upload_dir = storage.upload_dir('upload-seed')
    (upload_dir / 'rgb').mkdir(parents=True, exist_ok=True)
    (upload_dir / 'mapir').mkdir(parents=True, exist_ok=True)
    (upload_dir / 'rgb' / 'a.jpg').write_bytes(b'123')
    (upload_dir / 'mapir' / 'b.jpg').write_bytes(b'123')
    service = RunService(storage)

    record = service.create_run_record(_request('upload-seed'))
    assert Path(record.run_dir).exists()
    assert Path(record.logs_path).exists()
    assert record.progress_percent == 0
    assert record.stages

    loaded = service.load_run(record.run_id)
    assert loaded.dataset_name == 'Dataset 1'

    updated = service.update_status(record.run_id, status='running', outputs={'report_html': 'output/report/index.html'})
    assert updated.status == 'running'
    assert updated.outputs['report_html'].endswith('index.html')


def test_request_stop_marks_running_run_cancelled(tmp_path: Path, monkeypatch) -> None:
    storage = StorageService(project_root=tmp_path)
    upload_dir = storage.upload_dir('upload-seed')
    (upload_dir / 'rgb').mkdir(parents=True, exist_ok=True)
    (upload_dir / 'mapir').mkdir(parents=True, exist_ok=True)
    service = RunService(storage)
    monkeypatch.setattr(service, '_stop_odm_containers', lambda: None)

    record = service.create_run_record(_request('upload-seed'))
    service.update_status(record.run_id, status='running')

    stopped = service.request_stop(record.run_id)

    assert stopped.status == 'cancelled'
    assert stopped.current_stage == 'cancelled'
    assert stopped.finished_at is not None
    assert 'Run stopped by operator.' in stopped.errors
    assert stopped.errors.count('Run stopped by operator.') == 1


def test_delete_run_removes_only_runtime_run_dir(tmp_path: Path) -> None:
    storage = StorageService(project_root=tmp_path)
    upload_dir = storage.upload_dir('upload-seed')
    (upload_dir / 'rgb').mkdir(parents=True, exist_ok=True)
    (upload_dir / 'mapir').mkdir(parents=True, exist_ok=True)
    output_dir = tmp_path / 'output' / 'runs' / 'kept'
    output_dir.mkdir(parents=True)
    (output_dir / 'report.html').write_text('keep', encoding='utf-8')
    service = RunService(storage)
    record = service.create_run_record(_request('upload-seed'))
    service.update_status(record.run_id, status='completed')

    service.delete_run(record.run_id)

    assert not (storage.layout.runs_root / record.run_id).exists()
    assert upload_dir.exists()
    assert (output_dir / 'report.html').exists()


def test_archive_run_moves_runtime_record(tmp_path: Path) -> None:
    storage = StorageService(project_root=tmp_path)
    upload_dir = storage.upload_dir('upload-seed')
    (upload_dir / 'rgb').mkdir(parents=True, exist_ok=True)
    (upload_dir / 'mapir').mkdir(parents=True, exist_ok=True)
    service = RunService(storage)
    record = service.create_run_record(_request('upload-seed'))
    service.update_status(record.run_id, status='failed')

    archived = service.archive_run(record.run_id)

    assert archived == storage.layout.runtime_root / 'archived_runs' / record.run_id
    assert archived.exists()
    assert not (storage.layout.runs_root / record.run_id).exists()


def test_clear_stuck_active_runs_cancels_runs_without_live_thread(tmp_path: Path) -> None:
    storage = StorageService(project_root=tmp_path)
    upload_dir = storage.upload_dir('upload-seed')
    (upload_dir / 'rgb').mkdir(parents=True, exist_ok=True)
    (upload_dir / 'mapir').mkdir(parents=True, exist_ok=True)
    service = RunService(storage)
    record = service.create_run_record(_request('upload-seed'))
    service.update_status(record.run_id, status='running')

    cleared = service.clear_stuck_active_runs()

    assert [item.run_id for item in cleared] == [record.run_id]
    loaded = service.load_run(record.run_id)
    assert loaded.status == 'cancelled'
    assert 'Cleared stale active run.' in loaded.errors


def test_update_status_uses_storage_run_dir_for_legacy_record_paths(tmp_path: Path) -> None:
    storage = StorageService(project_root=tmp_path)
    service = RunService(storage)
    run_dir = storage.run_dir('legacy-run')
    legacy_dir = tmp_path / 'not-the-runtime-dir'
    storage.write_json(run_dir / 'status.json', {
        'run_id': 'legacy-run',
        'created_at': '2026-03-29T00:00:00Z',
        'updated_at': '2026-03-29T00:00:00Z',
        'started_at': None,
        'finished_at': None,
        'dataset_name': 'Dataset 1',
        'input_path': str(tmp_path / 'data' / 'uploads' / 'upload-seed'),
        'status': 'running',
        'progress_percent': 0,
        'current_stage': 'run_odm_rgb',
        'stage_message': 'Running ODM',
        'selected_steps': {'resize_images': False, 'run_odm': True, 'fetch_weather': False, 'generate_report': True},
        'parameters': {},
        'outputs': {},
        'errors': [],
        'stages': [],
        'logs_path': str(legacy_dir / 'run.log'),
        'run_name': None,
        'field_name': None,
        'run_dir': str(legacy_dir),
    })

    service.update_status('legacy-run', status='cancelled')

    assert service.load_run('legacy-run').status == 'cancelled'
    assert not (legacy_dir / 'status.json').exists()


def test_discover_outputs_copies_report_to_per_run_output(tmp_path: Path, monkeypatch) -> None:
    storage = StorageService(project_root=tmp_path)
    service = RunService(storage)
    run_dir = storage.run_dir('run-1')
    storage.write_json(run_dir / 'status.json', {
        'run_id': 'run-1',
        'created_at': '2026-03-29T00:00:00Z',
        'updated_at': '2026-03-29T00:00:00Z',
        'started_at': None,
        'finished_at': None,
        'dataset_name': 'Dataset 1',
        'input_path': str(tmp_path / 'data' / 'uploads' / 'upload-seed'),
        'status': 'running',
        'progress_percent': 0,
        'current_stage': 'generate_report',
        'stage_message': 'Generating report',
        'selected_steps': {'resize_images': False, 'run_odm': True, 'fetch_weather': False, 'generate_report': True},
        'parameters': {},
        'outputs': {},
        'errors': [],
        'stages': [],
        'logs_path': str(run_dir / 'run.log'),
        'run_name': 'Final Vineyard Report',
        'field_name': None,
        'run_dir': str(run_dir),
    })
    output_root = tmp_path / 'output'
    report_latest = output_root / 'report_latest.html'
    report_latest.parent.mkdir(parents=True, exist_ok=True)
    report_latest.write_text('<html></html>', encoding='utf-8')
    ndvi_dir = output_root / 'ndvi'
    ndvi_dir.mkdir(parents=True, exist_ok=True)
    (ndvi_dir / 'ndvi.tif').write_text('x', encoding='utf-8')

    monkeypatch.setattr('agrivision.services.run_service.load_config', lambda: {
        'paths': {
            'output_root': 'output',
            'ndvi_output': 'output/ndvi',
            'odm_project_root_rgb': 'odm_rgb',
            'odm_project_root_mapir': 'odm_mapir',
            'images_full': 'images/full',
            'images_full_mapir': 'images/full_mapir',
        }
    })

    outputs = service._discover_outputs(run_dir)
    saved_report = Path(outputs['report_html'])
    assert saved_report.exists()
    assert saved_report.parent == tmp_path / 'output' / 'runs' / 'run-1'
    assert saved_report.name == 'final-vineyard-report.html'


def test_report_filename_falls_back_to_system_timestamp(tmp_path: Path, monkeypatch) -> None:
    storage = StorageService(project_root=tmp_path)
    service = RunService(storage)
    run_dir = storage.run_dir('run-2')
    storage.write_json(run_dir / 'status.json', {
        'run_id': 'run-2',
        'created_at': '2026-03-29T00:00:00Z',
        'updated_at': '2026-03-29T00:00:00Z',
        'started_at': None,
        'finished_at': None,
        'dataset_name': 'Dataset 2',
        'input_path': str(tmp_path / 'data' / 'uploads' / 'upload-seed'),
        'status': 'running',
        'progress_percent': 0,
        'current_stage': 'generate_report',
        'stage_message': 'Generating report',
        'selected_steps': {'resize_images': False, 'run_odm': True, 'fetch_weather': False, 'generate_report': True},
        'parameters': {},
        'outputs': {},
        'errors': [],
        'stages': [],
        'logs_path': str(run_dir / 'run.log'),
        'run_name': None,
        'field_name': None,
        'run_dir': str(run_dir),
    })
    report_latest = tmp_path / 'output' / 'report_latest.html'
    report_latest.parent.mkdir(parents=True, exist_ok=True)
    report_latest.write_text('<html></html>', encoding='utf-8')

    monkeypatch.setattr('agrivision.services.run_service._timestamp_report_name', lambda: '2026-03-29_12-34-56')
    monkeypatch.setattr('agrivision.services.run_service.load_config', lambda: {
        'paths': {
            'output_root': 'output',
            'runs_output': 'output/runs',
            'ndvi_output': 'output/ndvi',
            'odm_project_root_rgb': 'odm_rgb',
            'odm_project_root_mapir': 'odm_mapir',
            'images_full': 'images/full',
            'images_full_mapir': 'images/full_mapir',
        }
    })

    outputs = service._discover_outputs(run_dir)
    assert Path(outputs['report_html']).name == '2026-03-29-12-34-56.html'
