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
                'generate_orthophoto': True,
                'fetch_weather': False,
                'generate_report': True,
            },
            'parameters': {'preset': 'default', 'notes': 'ok'},
        }
    )


def test_run_record_creation_and_status_update(tmp_path: Path) -> None:
    storage = StorageService(project_root=tmp_path)
    upload_dir = storage.upload_dir('upload-seed')
    (upload_dir / 'a.jpg').write_bytes(b'123')
    service = RunService(storage)

    record = service.create_run_record(_request('upload-seed'))
    assert Path(record.run_dir).exists()
    assert Path(record.logs_path).exists()
    loaded = service.load_run(record.run_id)
    assert loaded.dataset_name == 'Dataset 1'

    updated = service.update_status(record.run_id, status='running', outputs={'report_html': 'output/report/index.html'})
    assert updated.status == 'running'
    assert updated.outputs['report_html'].endswith('index.html')
