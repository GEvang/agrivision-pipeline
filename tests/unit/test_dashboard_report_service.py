from __future__ import annotations

import json
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


def test_latest_report_skips_preview_generation_by_default(tmp_path: Path) -> None:
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

    latest = report_service.latest_report()

    assert latest is not None
    assert latest.run_id == record.run_id
    assert latest.preview_path is None


def test_report_quality_summary_reads_metadata(tmp_path: Path) -> None:
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
    ndvi_meta = tmp_path / 'metadata.json'
    grid_meta = tmp_path / 'grid_metadata.json'
    ndvi_meta.write_text(
        json.dumps(
            {
                'source': {'dataset': 'MAPIR'},
                'index': {'index_name': 'Vegetation Index', 'index_mode': 'nir_green'},
                'valid_pixels': {'percent': 42.5},
                'distribution': {
                    'mean': 0.1,
                    'median': 0.09,
                    'saturated_high_percent': 0.0,
                    'saturated_low_percent': 0.0,
                },
                'quality_flags': [],
            }
        ),
        encoding='utf-8',
    )
    grid_meta.write_text(
        json.dumps(
            {
                'classification_mode': 'percentile_calibrated',
                'thresholds_used': {'poor_max': 0.02, 'medium_max': 0.04},
            }
        ),
        encoding='utf-8',
    )
    service.update_status(
        record.run_id,
        status='completed',
        outputs={
            'report_html': str(tmp_path / 'report.html'),
            'ndvi_metadata': str(ndvi_meta),
            'grid_metadata': str(grid_meta),
        },
    )
    report = ReportService(run_service=service).get_report(record.run_id)

    assert report.quality['state'] == 'warn'
    assert report.quality['source_dataset'] == 'MAPIR'
    assert report.quality['classification_mode'] == 'percentile_calibrated'
    assert report.quality['poor_max'] == 0.02
    assert 'Low valid vegetation-index coverage.' in report.quality['flags']


def test_report_quality_summary_ignores_global_metadata_without_run_outputs(tmp_path: Path) -> None:
    storage = StorageService(project_root=tmp_path)
    upload_dir = storage.upload_dir('upload-seed')
    (upload_dir / 'a.jpg').write_bytes(b'123')
    service = RunService(storage)
    record = service.create_run_record(
        RunCreateRequest.model_validate(
            {
                'run_name': 'Orthophoto Run',
                'dataset_name': 'Dataset R',
                'upload_run_id': 'upload-seed',
                'selected_steps': {
                    'resize_images': False,
                    'run_odm': True,
                    'fetch_weather': False,
                    'run_irrigation': False,
                    'run_pdm': False,
                    'generate_report': False,
                },
                'parameters': {},
            }
        )
    )
    global_ndvi = tmp_path / 'output' / 'ndvi'
    global_ndvi.mkdir(parents=True)
    (global_ndvi / 'metadata.json').write_text(
        json.dumps({'valid_pixels': {'percent': 99}, 'distribution': {'mean': 0.9}}),
        encoding='utf-8',
    )
    (global_ndvi / 'grid_metadata.json').write_text(
        json.dumps({'classification_mode': 'percentile_calibrated'}),
        encoding='utf-8',
    )
    service.update_status(record.run_id, status='completed', outputs={})

    report = ReportService(run_service=service).get_report(record.run_id)

    assert report.report_path is None
    assert report.quality == {}
