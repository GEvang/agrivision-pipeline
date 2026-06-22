from __future__ import annotations

from pathlib import Path

from agrivision.app.schemas.runs import RunCreateRequest
from agrivision.services.run_service import RunService, RunStartBlocked
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


def test_start_run_blocks_when_another_run_is_running(tmp_path: Path) -> None:
    storage = StorageService(project_root=tmp_path)
    upload_dir = storage.upload_dir('upload-seed')
    (upload_dir / 'rgb').mkdir(parents=True, exist_ok=True)
    (upload_dir / 'mapir').mkdir(parents=True, exist_ok=True)
    service = RunService(storage)
    active = service.create_run_record(_request('upload-seed'))
    pending = service.create_run_record(_request('upload-seed'))
    service.update_status(active.run_id, status='running')

    try:
        service.start_run(pending.run_id)
    except RunStartBlocked as exc:
        message = str(exc)
    else:
        raise AssertionError('Expected active run to block a new run')

    assert active.run_id in message
    assert service.load_run(pending.run_id).status == 'queued'


def test_start_run_blocks_when_another_run_is_queued(tmp_path: Path) -> None:
    storage = StorageService(project_root=tmp_path)
    upload_dir = storage.upload_dir('upload-seed')
    (upload_dir / 'rgb').mkdir(parents=True, exist_ok=True)
    (upload_dir / 'mapir').mkdir(parents=True, exist_ok=True)
    service = RunService(storage)
    queued = service.create_run_record(_request('upload-seed'))
    pending = service.create_run_record(_request('upload-seed'))

    try:
        service.start_run(pending.run_id)
    except RunStartBlocked as exc:
        message = str(exc)
    else:
        raise AssertionError('Expected queued run to block a new run')

    assert queued.run_id in message
    assert service.load_run(pending.run_id).status == 'queued'


def test_start_run_blocks_non_odm_runs_while_another_run_is_active(tmp_path: Path) -> None:
    storage = StorageService(project_root=tmp_path)
    upload_dir = storage.upload_dir('upload-seed')
    (upload_dir / 'rgb').mkdir(parents=True, exist_ok=True)
    (upload_dir / 'mapir').mkdir(parents=True, exist_ok=True)
    service = RunService(storage)
    active = service.create_run_record(_request('upload-seed'))
    reuse_request = RunCreateRequest.model_validate(
        {
            'run_name': 'Reuse orthophotos',
            'dataset_name': 'Dataset 1',
            'upload_run_id': 'upload-seed',
            'selected_steps': {
                'resize_images': False,
                'run_odm': False,
                'fetch_weather': True,
                'run_irrigation': False,
                'run_pdm': False,
                'generate_report': True,
            },
            'parameters': {'source_orthophoto_run_id': active.run_id},
        }
    )
    pending = service.create_run_record(reuse_request)
    service.update_status(active.run_id, status='running')

    try:
        service.start_run(pending.run_id)
    except RunStartBlocked as exc:
        message = str(exc)
    else:
        raise AssertionError('Expected active run to block non-ODM run')

    assert active.run_id in message


def test_start_run_allows_new_run_after_terminal_status(tmp_path: Path) -> None:
    storage = StorageService(project_root=tmp_path)
    upload_dir = storage.upload_dir('upload-seed')
    (upload_dir / 'rgb').mkdir(parents=True, exist_ok=True)
    (upload_dir / 'mapir').mkdir(parents=True, exist_ok=True)
    service = RunService(storage)
    finished = service.create_run_record(_request('upload-seed'))
    pending = service.create_run_record(_request('upload-seed'))
    service.update_status(finished.run_id, status='completed')

    calls: list[str] = []

    def fake_execute(run_id: str) -> None:
        calls.append(run_id)

    service._execute_run = fake_execute  # type: ignore[method-assign]
    result = service.start_run(pending.run_id)

    assert result.status == 'running'
    assert calls == [pending.run_id]


def test_start_run_allows_new_run_after_failed_status(tmp_path: Path) -> None:
    storage = StorageService(project_root=tmp_path)
    upload_dir = storage.upload_dir('upload-seed')
    (upload_dir / 'rgb').mkdir(parents=True, exist_ok=True)
    (upload_dir / 'mapir').mkdir(parents=True, exist_ok=True)
    service = RunService(storage)
    failed = service.create_run_record(_request('upload-seed'))
    pending = service.create_run_record(_request('upload-seed'))
    service.update_status(failed.run_id, status='failed')

    calls: list[str] = []

    def fake_execute(run_id: str) -> None:
        calls.append(run_id)

    service._execute_run = fake_execute  # type: ignore[method-assign]
    result = service.start_run(pending.run_id)

    assert result.status == 'running'
    assert calls == [pending.run_id]


def test_start_run_allows_new_run_after_cancelled_status(tmp_path: Path) -> None:
    storage = StorageService(project_root=tmp_path)
    upload_dir = storage.upload_dir('upload-seed')
    (upload_dir / 'rgb').mkdir(parents=True, exist_ok=True)
    (upload_dir / 'mapir').mkdir(parents=True, exist_ok=True)
    service = RunService(storage)
    cancelled = service.create_run_record(_request('upload-seed'))
    pending = service.create_run_record(_request('upload-seed'))
    service.update_status(cancelled.run_id, status='cancelled')

    calls: list[str] = []

    def fake_execute(run_id: str) -> None:
        calls.append(run_id)

    service._execute_run = fake_execute  # type: ignore[method-assign]
    result = service.start_run(pending.run_id)

    assert result.status == 'running'
    assert calls == [pending.run_id]


def test_mark_start_blocked_records_clear_operator_message(tmp_path: Path) -> None:
    storage = StorageService(project_root=tmp_path)
    upload_dir = storage.upload_dir('upload-seed')
    (upload_dir / 'rgb').mkdir(parents=True, exist_ok=True)
    (upload_dir / 'mapir').mkdir(parents=True, exist_ok=True)
    service = RunService(storage)
    record = service.create_run_record(_request('upload-seed'))

    blocked = service.mark_start_blocked(record.run_id, 'Another run is already active (run-123).')

    assert blocked.status == 'cancelled'
    assert blocked.current_stage == 'blocked'
    assert blocked.stage_message == 'Another run is already active (run-123).'
    assert blocked.finished_at is not None
    assert blocked.errors == ['Another run is already active (run-123).']
    assert all(stage.state != 'running' for stage in blocked.stages)


def test_odm_only_run_does_not_include_services(tmp_path: Path) -> None:
    storage = StorageService(project_root=tmp_path)
    upload_dir = storage.upload_dir('upload-seed')
    (upload_dir / 'rgb').mkdir(parents=True, exist_ok=True)
    (upload_dir / 'mapir').mkdir(parents=True, exist_ok=True)
    service = RunService(storage)
    request = RunCreateRequest.model_validate(
        {
            'run_name': 'Orthophotos',
            'dataset_name': 'Dataset 1',
            'upload_run_id': 'upload-seed',
            'selected_steps': {
                'resize_images': False,
                'run_odm': True,
                'fetch_weather': False,
                'run_irrigation': False,
                'run_pdm': False,
                'generate_report': False,
            },
        }
    )

    record = service.create_run_record(request)
    stage_keys = [stage.key for stage in record.stages]

    assert 'run_odm_rgb' in stage_keys
    assert 'compute_ndvi' not in stage_keys
    assert 'generate_grid' not in stage_keys
    assert 'fetch_weather' not in stage_keys
    assert 'irrigation_enrichment' not in stage_keys
    assert 'pdm_enrichment' not in stage_keys


def test_request_stop_marks_running_run_cancelled(tmp_path: Path, monkeypatch) -> None:
    storage = StorageService(project_root=tmp_path)
    upload_dir = storage.upload_dir('upload-seed')
    (upload_dir / 'rgb').mkdir(parents=True, exist_ok=True)
    (upload_dir / 'mapir').mkdir(parents=True, exist_ok=True)
    service = RunService(storage)
    monkeypatch.setattr(service, '_stop_odm_containers', lambda: None)

    record = service.create_run_record(_request('upload-seed'))
    service.update_status(record.run_id, status='running')
    service.update_stage(record.run_id, 'stage_inputs', 'completed', 'Inputs staged')
    service.update_stage(record.run_id, 'run_odm_rgb', 'running', 'Running ODM RGB')

    stopped = service.request_stop(record.run_id)

    assert stopped.status == 'cancelled'
    assert stopped.current_stage == 'cancelled'
    assert stopped.finished_at is not None
    assert 'Run stopped by operator.' in stopped.errors
    assert stopped.errors.count('Run stopped by operator.') == 1
    stage_states = {stage.key: stage.state for stage in stopped.stages}
    assert stage_states['run_odm_rgb'] == 'cancelled'
    assert stage_states['run_odm_mapir'] == 'skipped'
    assert all(stage.state != 'running' for stage in stopped.stages)


def test_failed_run_stores_diagnostic_summary_and_raw_log(tmp_path: Path, monkeypatch) -> None:
    storage = StorageService(project_root=tmp_path)
    upload_dir = storage.upload_dir('upload-seed')
    (upload_dir / 'rgb').mkdir(parents=True, exist_ok=True)
    (upload_dir / 'mapir').mkdir(parents=True, exist_ok=True)
    service = RunService(storage)
    record = service.create_run_record(_request('upload-seed'))

    monkeypatch.setattr(service, 'stage_inputs_for_run', lambda run_id: None)
    monkeypatch.setattr(service, '_discover_outputs', lambda run_dir: {})

    def fail_pipeline(**kwargs) -> None:
        kwargs['progress_callback']('run_odm_rgb', 'Running ODM RGB')
        raise RuntimeError('ODM-RGB failed with exit code 139. Docker mount args were --volumes-from app.')

    monkeypatch.setattr('agrivision.services.run_service.run_full_pipeline', fail_pipeline)

    failed = service.launch_run(record.run_id)
    log_text = Path(failed.logs_path).read_text(encoding='utf-8')

    assert failed.status == 'failed'
    assert failed.finished_at is not None
    assert 'crashed during reconstruction' in failed.stage_message
    assert failed.errors == [failed.stage_message]
    assert 'Raw error: ODM-RGB failed with exit code 139' in log_text
    stage_states = {stage.key: stage.state for stage in failed.stages}
    assert stage_states['run_odm_rgb'] == 'failed'
    assert stage_states['run_odm_mapir'] == 'skipped'
    assert all(stage.state != 'running' for stage in failed.stages)


def test_launch_run_does_not_attach_stale_global_outputs(tmp_path: Path, monkeypatch) -> None:
    storage = StorageService(project_root=tmp_path)
    upload_dir = storage.upload_dir('upload-seed')
    (upload_dir / 'rgb').mkdir(parents=True, exist_ok=True)
    (upload_dir / 'mapir').mkdir(parents=True, exist_ok=True)
    service = RunService(storage)
    record = service.create_run_record(_request('upload-seed'))

    output_root = tmp_path / 'output'
    ndvi_dir = output_root / 'ndvi'
    report_dir = output_root / 'report'
    rgb_ortho = tmp_path / 'odm_rgb' / 'project' / 'odm_orthophoto' / 'odm_orthophoto.tif'
    mapir_ortho = tmp_path / 'odm_mapir' / 'project' / 'odm_orthophoto' / 'odm_orthophoto.tif'

    ndvi_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    rgb_ortho.parent.mkdir(parents=True, exist_ok=True)
    mapir_ortho.parent.mkdir(parents=True, exist_ok=True)

    (output_root / 'report_latest.html').write_text('<html>stale latest</html>', encoding='utf-8')
    (report_dir / 'index.html').write_text('<html>stale report</html>', encoding='utf-8')
    (ndvi_dir / 'ndvi.tif').write_text('stale ndvi', encoding='utf-8')
    (ndvi_dir / 'metadata.json').write_text('{}', encoding='utf-8')
    (ndvi_dir / 'grid_metadata.json').write_text('{}', encoding='utf-8')
    rgb_ortho.write_text('stale rgb', encoding='utf-8')
    mapir_ortho.write_text('stale mapir', encoding='utf-8')

    monkeypatch.setattr(service, 'stage_inputs_for_run', lambda run_id: None)
    monkeypatch.setattr('agrivision.services.run_service.run_full_pipeline', lambda **kwargs: None)
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

    completed = service.launch_run(record.run_id)

    assert completed.status == 'completed'
    assert completed.outputs == {}
    assert not (output_root / 'report_latest.html').exists()
    assert not (report_dir / 'index.html').exists()
    assert not (ndvi_dir / 'ndvi.tif').exists()
    assert not rgb_ortho.exists()
    assert not mapir_ortho.exists()


def test_finalize_run_status_is_idempotent_for_terminal_runs(tmp_path: Path) -> None:
    storage = StorageService(project_root=tmp_path)
    upload_dir = storage.upload_dir('upload-seed')
    (upload_dir / 'rgb').mkdir(parents=True, exist_ok=True)
    (upload_dir / 'mapir').mkdir(parents=True, exist_ok=True)
    service = RunService(storage)
    record = service.create_run_record(_request('upload-seed'))
    service.update_status(record.run_id, status='running')
    service.update_stage(record.run_id, 'run_odm_rgb', 'running', 'Running ODM RGB')

    first = service.finalize_run_status(
        record.run_id,
        status='cancelled',
        current_stage='cancelled',
        stage_message='Run stopped by operator.',
        error_message='Run stopped by operator.',
        running_stage_state='cancelled',
        running_stage_message='Stopped by operator.',
    )
    second = service.finalize_run_status(
        record.run_id,
        status='cancelled',
        current_stage='cancelled',
        stage_message='Run stopped by operator.',
        error_message='Run stopped by operator.',
        running_stage_state='cancelled',
        running_stage_message='Stopped by operator.',
    )

    assert second.finished_at == first.finished_at
    assert second.errors == ['Run stopped by operator.']
    assert all(stage.state != 'running' for stage in second.stages)


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


def test_delete_run_removes_matching_run_output_dir(tmp_path: Path) -> None:
    storage = StorageService(project_root=tmp_path)
    upload_dir = storage.upload_dir('upload-seed')
    (upload_dir / 'rgb').mkdir(parents=True, exist_ok=True)
    (upload_dir / 'mapir').mkdir(parents=True, exist_ok=True)
    service = RunService(storage)
    record = service.create_run_record(_request('upload-seed'))
    service.update_status(record.run_id, status='completed')
    run_output_dir = tmp_path / 'output' / 'runs' / record.run_id
    run_output_dir.mkdir(parents=True)
    (run_output_dir / 'artifact.txt').write_text('remove', encoding='utf-8')

    service.delete_run(record.run_id)

    assert not run_output_dir.exists()


def test_clear_incomplete_removes_failed_and_cancelled_runs(tmp_path: Path) -> None:
    storage = StorageService(project_root=tmp_path)
    upload_dir = storage.upload_dir('upload-seed')
    (upload_dir / 'rgb').mkdir(parents=True, exist_ok=True)
    (upload_dir / 'mapir').mkdir(parents=True, exist_ok=True)
    service = RunService(storage)
    failed = service.create_run_record(_request('upload-seed'))
    cancelled = service.create_run_record(_request('upload-seed'))
    completed = service.create_run_record(_request('upload-seed'))
    service.update_status(failed.run_id, status='failed')
    service.update_status(cancelled.run_id, status='cancelled')
    service.update_status(completed.run_id, status='completed')

    removed = service.clear_incomplete_runs()

    assert removed == 2
    remaining = {run.run_id for run in service.list_runs()}
    assert remaining == {completed.run_id}


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


def test_list_runs_surfaces_corrupted_status_records(tmp_path: Path) -> None:
    storage = StorageService(project_root=tmp_path)
    service = RunService(storage)
    run_dir = storage.run_dir('broken-run')
    (run_dir / 'status.json').write_text('{"run_id": "broken-run", "dataset_name": "Broken"', encoding='utf-8')

    runs = service.list_runs()

    assert [run.run_id for run in runs] == ['broken-run']
    broken = runs[0]
    assert broken.status == 'failed'
    assert broken.current_stage == 'corrupted'
    assert broken.stage_message == RunService.CORRUPTED_RUN_MESSAGE
    assert 'requires manual cleanup' in broken.errors[0]


def test_load_run_returns_placeholder_for_corrupted_status_record(tmp_path: Path) -> None:
    storage = StorageService(project_root=tmp_path)
    service = RunService(storage)
    run_dir = storage.run_dir('broken-run')
    (run_dir / 'status.json').write_text('{"status": "running"', encoding='utf-8')

    broken = service.load_run('broken-run')

    assert broken.run_id == 'broken-run'
    assert broken.status == 'failed'
    assert broken.current_stage == 'corrupted'
    assert broken.finished_at is not None


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
    rgb_ortho = tmp_path / 'odm_rgb' / 'project' / 'odm_orthophoto' / 'odm_orthophoto.tif'
    rgb_ortho.parent.mkdir(parents=True)
    rgb_ortho.write_text('rgb', encoding='utf-8')
    mapir_ortho = tmp_path / 'odm_mapir' / 'project' / 'odm_orthophoto' / 'odm_orthophoto.tif'
    mapir_ortho.parent.mkdir(parents=True)
    mapir_ortho.write_text('mapir', encoding='utf-8')

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
    assert Path(outputs['orthophoto_rgb']).parent == tmp_path / 'output' / 'runs' / 'run-1' / 'orthophotos'
    assert Path(outputs['orthophoto_mapir']).name == 'orthophoto_mapir.tif'


def test_orthophoto_only_outputs_do_not_attach_stale_analysis_files(tmp_path: Path, monkeypatch) -> None:
    storage = StorageService(project_root=tmp_path)
    service = RunService(storage)
    run_dir = storage.run_dir('ortho-only')
    storage.write_json(run_dir / 'status.json', {
        'run_id': 'ortho-only',
        'created_at': '2026-03-29T00:00:00Z',
        'updated_at': '2026-03-29T00:00:00Z',
        'started_at': None,
        'finished_at': None,
        'dataset_name': 'Dataset 1',
        'input_path': str(tmp_path / 'data' / 'uploads' / 'upload-seed'),
        'status': 'running',
        'progress_percent': 0,
        'current_stage': 'run_odm_mapir',
        'stage_message': 'Running ODM',
        'selected_steps': {
            'resize_images': False,
            'run_odm': True,
            'fetch_weather': False,
            'run_irrigation': False,
            'run_pdm': False,
            'generate_report': False,
        },
        'parameters': {},
        'outputs': {},
        'errors': [],
        'stages': [],
        'logs_path': str(run_dir / 'run.log'),
        'run_name': 'Orthos',
        'field_name': None,
        'run_dir': str(run_dir),
    })
    output_root = tmp_path / 'output'
    (output_root / 'ndvi').mkdir(parents=True, exist_ok=True)
    (output_root / 'report_latest.html').write_text('<html>stale</html>', encoding='utf-8')
    (output_root / 'ndvi' / 'ndvi.tif').write_text('stale ndvi', encoding='utf-8')
    (output_root / 'ndvi' / 'metadata.json').write_text('{}', encoding='utf-8')
    (output_root / 'ndvi' / 'grid_metadata.json').write_text('{}', encoding='utf-8')
    rgb_ortho = tmp_path / 'odm_rgb' / 'project' / 'odm_orthophoto' / 'odm_orthophoto.tif'
    rgb_ortho.parent.mkdir(parents=True)
    rgb_ortho.write_text('rgb', encoding='utf-8')
    mapir_ortho = tmp_path / 'odm_mapir' / 'project' / 'odm_orthophoto' / 'odm_orthophoto.tif'
    mapir_ortho.parent.mkdir(parents=True)
    mapir_ortho.write_text('mapir', encoding='utf-8')

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

    assert sorted(outputs) == ['orthophoto_mapir', 'orthophoto_rgb']
    assert Path(outputs['orthophoto_rgb']).parent == tmp_path / 'output' / 'runs' / 'ortho-only' / 'orthophotos'


def test_stage_saved_orthophotos_for_run_restores_pipeline_inputs(tmp_path: Path, monkeypatch) -> None:
    storage = StorageService(project_root=tmp_path)
    service = RunService(storage)
    source_dir = storage.run_dir('ortho-run')
    saved_rgb = tmp_path / 'output' / 'runs' / 'ortho-run' / 'orthophotos' / 'orthophoto_rgb.tif'
    saved_mapir = tmp_path / 'output' / 'runs' / 'ortho-run' / 'orthophotos' / 'orthophoto_mapir.tif'
    saved_rgb.parent.mkdir(parents=True)
    saved_rgb.write_text('rgb', encoding='utf-8')
    saved_mapir.write_text('mapir', encoding='utf-8')
    storage.write_json(source_dir / 'status.json', {
        'run_id': 'ortho-run',
        'created_at': '2026-03-29T00:00:00Z',
        'updated_at': '2026-03-29T00:00:00Z',
        'started_at': None,
        'finished_at': None,
        'dataset_name': 'Dataset 1',
        'input_path': str(tmp_path / 'data' / 'uploads' / 'upload-seed'),
        'status': 'completed',
        'progress_percent': 100,
        'current_stage': 'completed',
        'stage_message': 'Done',
        'selected_steps': {'resize_images': False, 'run_odm': True, 'fetch_weather': False, 'generate_report': False},
        'parameters': {},
        'outputs': {'orthophoto_rgb': str(saved_rgb), 'orthophoto_mapir': str(saved_mapir)},
        'errors': [],
        'stages': [],
        'logs_path': str(source_dir / 'run.log'),
        'run_name': None,
        'field_name': None,
        'run_dir': str(source_dir),
    })
    monkeypatch.setattr('agrivision.services.run_service.get_project_root', lambda: tmp_path)
    monkeypatch.setattr('agrivision.services.run_service.load_config', lambda: {
        'paths': {
            'odm_project_root_rgb': 'data/odm_project_rgb',
            'odm_project_root_mapir': 'data/odm_project_mapir',
        }
    })

    service.stage_saved_orthophotos_for_run('ortho-run')

    assert (tmp_path / 'data' / 'odm_project_rgb' / 'project' / 'odm_orthophoto' / 'odm_orthophoto.tif').read_text(encoding='utf-8') == 'rgb'
    assert (tmp_path / 'data' / 'odm_project_mapir' / 'project' / 'odm_orthophoto' / 'odm_orthophoto.tif').read_text(encoding='utf-8') == 'mapir'


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
