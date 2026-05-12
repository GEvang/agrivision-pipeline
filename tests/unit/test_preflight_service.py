from __future__ import annotations

from pathlib import Path

from agrivision.app.schemas.runs import RunCreateRequest
from agrivision.services.preflight_service import PreflightService
from agrivision.services.storage_service import StorageService


def _request(upload_run_id: str, *, run_odm: bool = False, fetch_weather: bool = False, run_pdm: bool = False) -> RunCreateRequest:
    return RunCreateRequest.model_validate(
        {
            'run_name': 'Preflight',
            'dataset_name': 'Dataset',
            'upload_run_id': upload_run_id,
            'selected_steps': {
                'run_odm': run_odm,
                'fetch_weather': fetch_weather,
                'run_pdm': run_pdm,
                'generate_report': True,
            },
            'parameters': {},
        }
    )


def test_existing_orthophoto_mode_blocks_when_no_orthophoto_exists(tmp_path: Path, monkeypatch) -> None:
    storage = StorageService(project_root=tmp_path)
    upload_dir = storage.upload_dir('upload-1')
    storage.write_json(
        upload_dir / 'manifest.json',
        {'dataset_name': 'Dataset', 'rgb_files': ['a.jpg', 'b.jpg'], 'mapir_files': ['m1.jpg', 'm2.jpg']},
    )
    monkeypatch.setattr('agrivision.services.preflight_service.get_project_root', lambda: tmp_path)
    monkeypatch.setattr(
        'agrivision.services.preflight_service.load_config',
        lambda: {
            'paths': {
                'odm_project_root_rgb': 'data/odm_project_rgb',
                'odm_project_root_mapir': 'data/odm_project_mapir',
            },
            'irrigation': {'base_url': 'http://example'},
        },
    )
    service = PreflightService(storage)
    monkeypatch.setattr(service, '_url_check', lambda name, base_url: service._check(name, 'ok', 'HTTP 200'))

    result = service.validate(_request('upload-1', run_odm=False))

    assert result['ok'] is False
    assert 'Existing orthophoto mode needs an RGB or MAPIR orthophoto already generated.' in result['blockers']


def test_existing_orthophoto_mode_passes_with_rgb_orthophoto(tmp_path: Path, monkeypatch) -> None:
    storage = StorageService(project_root=tmp_path)
    upload_dir = storage.upload_dir('upload-1')
    storage.write_json(
        upload_dir / 'manifest.json',
        {'dataset_name': 'Dataset', 'rgb_files': ['a.jpg', 'b.jpg'], 'mapir_files': ['m1.jpg', 'm2.jpg']},
    )
    ortho = tmp_path / 'data' / 'odm_project_rgb' / 'project' / 'odm_orthophoto' / 'odm_orthophoto.tif'
    ortho.parent.mkdir(parents=True)
    ortho.write_text('ortho', encoding='utf-8')
    monkeypatch.setattr('agrivision.services.preflight_service.get_project_root', lambda: tmp_path)
    monkeypatch.setattr(
        'agrivision.services.preflight_service.load_config',
        lambda: {
            'paths': {
                'odm_project_root_rgb': 'data/odm_project_rgb',
                'odm_project_root_mapir': 'data/odm_project_mapir',
            },
            'irrigation': {'base_url': 'http://example'},
        },
    )
    service = PreflightService(storage)
    monkeypatch.setattr(service, '_url_check', lambda name, base_url: service._check(name, 'ok', 'HTTP 200'))

    result = service.validate(_request('upload-1', run_odm=False))

    assert result['ok'] is True
