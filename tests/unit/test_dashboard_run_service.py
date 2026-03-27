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


def test_discover_outputs_finds_report_latest(tmp_path: Path, monkeypatch) -> None:
    storage = StorageService(project_root=tmp_path)
    service = RunService(storage)
    run_dir = storage.run_dir('run-1')
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
    assert outputs['report_html'].endswith('report_latest.html')
