from __future__ import annotations

import json
import zipfile
from pathlib import Path

from agrivision.app.schemas.runs import RunCreateRequest
from agrivision.services.export_service import RunExportService
from agrivision.services.run_service import RunService
from agrivision.services.storage_service import StorageService


def test_build_package_includes_run_and_quality_artifacts(tmp_path: Path) -> None:
    storage = StorageService(project_root=tmp_path)
    upload_dir = storage.upload_dir('upload-seed')
    (upload_dir / 'rgb').mkdir(parents=True)
    (upload_dir / 'mapir').mkdir(parents=True)
    service = RunService(storage)
    record = service.create_run_record(
        RunCreateRequest.model_validate(
            {
                'run_name': 'Export Run',
                'dataset_name': 'Dataset',
                'upload_run_id': 'upload-seed',
                'selected_steps': {'run_odm': False, 'fetch_weather': False, 'generate_report': True},
                'parameters': {},
            }
        )
    )
    workspace = service.workspace_for_record(record)
    report = workspace.output_root / 'report_latest.html'
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text('<html><head></head><body><img src="ndvi/ndvi_color.png" /></body></html>', encoding='utf-8')
    ndvi_dir = workspace.ndvi_output
    ndvi_dir.mkdir(parents=True)
    (ndvi_dir / 'metadata.json').write_text(json.dumps({'quality': 'ok'}), encoding='utf-8')
    (ndvi_dir / 'grid_metadata.json').write_text(json.dumps({'grid': {}}), encoding='utf-8')
    (ndvi_dir / 'ndvi_grid_cells.csv').write_text('cell,value\nA1,1\n', encoding='utf-8')
    (ndvi_dir / 'ndvi_grid_overlay.png').write_bytes(b'png')
    (ndvi_dir / 'ndvi_color.png').write_bytes(b'png')
    service.update_status(
        record.run_id,
        status='completed',
        outputs={'report_html': str(report), 'ndvi_metadata': str(ndvi_dir / 'metadata.json')},
    )

    package = RunExportService(run_service=service, storage=storage).build_package(record.run_id)

    with zipfile.ZipFile(package) as archive:
        names = set(archive.namelist())
        assert 'manifest.json' in names
        assert 'metadata/run_metadata.jsonld' in names
        assert 'run/status.json' in names
        assert 'run/params.json' in names
        assert 'report/report.html' in names
        assert 'report-assets/report_latest.html' in names
        assert 'report-assets/ndvi/ndvi_color.png' in names
        assert 'quality/metadata.json' in names
        assert 'quality/grid_metadata.json' in names
        assert 'quality/grid_cells.csv' in names
        assert 'quality/grid_overlay.png' in names
        report_html = archive.read('report/report.html').decode('utf-8')
        assert '<base href="../report-assets/">' in report_html
        metadata = json.loads(archive.read('metadata/run_metadata.jsonld'))
        assert metadata['@id'] == f'urn:openagri:agrivision:run:{record.run_id}'
        assert metadata['dataset']['@type'] == 'AgriculturalDataset'
        assert any(item['contentUrl'] == 'report/report.html' for item in metadata['hasPart'])
