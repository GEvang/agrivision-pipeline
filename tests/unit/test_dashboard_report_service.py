from __future__ import annotations

from pathlib import Path

from PIL import Image

from agrivision.app.schemas.runs import RunCreateRequest
from agrivision.services.report_service import ReportService
from agrivision.services.run_service import RunService
from agrivision.services.storage_service import StorageService


def test_report_listing_and_preview_generation(tmp_path: Path) -> None:
    storage = StorageService(project_root=tmp_path)
    upload_dir = storage.upload_dir('upload-seed')
    (upload_dir / 'a.jpg').write_bytes(b'123')
    service = RunService(storage)
    record = service.create_run_record(
        RunCreateRequest.model_validate(
            {
                'run_name': 'Report Run',
                'dataset_name': 'Dataset R',
                'upload_run_id': 'upload-seed',
                'selected_steps': {},
                'parameters': {},
            }
        )
    )
    artifact = tmp_path / 'ortho.tif'
    Image.new('RGB', (20, 20)).save(artifact)
    service.update_status(record.run_id, status='completed', outputs={'orthophoto_rgb': str(artifact), 'report_html': str(tmp_path / 'report.html')})
    report_service = ReportService(run_service=service)

    items = report_service.list_reports()
    assert len(items) == 1
    assert items[0].preview_path is not None
    assert Path(items[0].preview_path).exists()
