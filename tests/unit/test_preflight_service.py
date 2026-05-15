from __future__ import annotations

import shutil
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


def _config() -> dict:
    return {
        'app': {
            'min_free_disk_gb': 50,
        },
        'paths': {
            'odm_project_root_rgb': 'data/odm_project_rgb',
            'odm_project_root_mapir': 'data/odm_project_mapir',
        },
        'irrigation': {'base_url': 'http://example'},
    }


def test_existing_orthophoto_mode_blocks_when_no_orthophoto_exists(tmp_path: Path, monkeypatch) -> None:
    storage = StorageService(project_root=tmp_path)
    upload_dir = storage.upload_dir('upload-1')
    storage.write_json(
        upload_dir / 'manifest.json',
        {'dataset_name': 'Dataset', 'rgb_files': ['a.jpg', 'b.jpg'], 'mapir_files': ['m1.jpg', 'm2.jpg']},
    )
    monkeypatch.setattr('agrivision.services.preflight_service.get_project_root', lambda: tmp_path)
    monkeypatch.setattr('agrivision.services.preflight_service.load_config', _config)
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
    monkeypatch.setattr('agrivision.services.preflight_service.load_config', _config)
    service = PreflightService(storage)
    monkeypatch.setattr(service, '_url_check', lambda name, base_url: service._check(name, 'ok', 'HTTP 200'))

    result = service.validate(_request('upload-1', run_odm=False))

    assert result['ok'] is True


def test_existing_orthophoto_mode_passes_with_saved_orthophoto_run(tmp_path: Path, monkeypatch) -> None:
    storage = StorageService(project_root=tmp_path)
    upload_dir = storage.upload_dir('upload-1')
    storage.write_json(
        upload_dir / 'manifest.json',
        {'dataset_name': 'Dataset', 'rgb_files': ['a.jpg', 'b.jpg'], 'mapir_files': ['m1.jpg', 'm2.jpg']},
    )
    saved_ortho = tmp_path / 'output' / 'runs' / 'ortho-run' / 'orthophotos' / 'orthophoto_rgb.tif'
    saved_ortho.parent.mkdir(parents=True)
    saved_ortho.write_text('rgb', encoding='utf-8')
    run_dir = storage.run_dir('ortho-run')
    storage.write_json(
        run_dir / 'status.json',
        {
            'outputs': {'orthophoto_rgb': str(saved_ortho)},
        },
    )
    monkeypatch.setattr('agrivision.services.preflight_service.load_config', _config)
    service = PreflightService(storage)
    request = RunCreateRequest.model_validate(
        {
            **_request('upload-1', run_odm=False).model_dump(),
            'parameters': {'source_orthophoto_run_id': 'ortho-run'},
        }
    )

    result = service.validate(request)

    assert result['ok'] is True
    assert any(item['name'] == 'Saved RGB orthophoto' and item['state'] == 'ok' for item in result['checks'])


def test_odm_preflight_blocks_when_disk_space_is_too_low(tmp_path: Path, monkeypatch) -> None:
    storage = StorageService(project_root=tmp_path)
    upload_dir = storage.upload_dir('upload-1')
    storage.write_json(
        upload_dir / 'manifest.json',
        {'dataset_name': 'Dataset', 'rgb_files': ['a.jpg', 'b.jpg'], 'mapir_files': ['m1.jpg', 'm2.jpg']},
    )

    def config() -> dict:
        cfg = _config()
        cfg['app']['min_free_disk_gb'] = 100
        return cfg

    monkeypatch.setattr('agrivision.services.preflight_service.get_project_root', lambda: tmp_path)
    monkeypatch.setattr('agrivision.services.preflight_service.load_config', config)
    monkeypatch.setattr(
        'agrivision.services.preflight_service.shutil.disk_usage',
        lambda path: shutil._ntuple_diskusage(total=200 * 1024**3, used=150 * 1024**3, free=50 * 1024**3),
    )
    service = PreflightService(storage)
    monkeypatch.setattr(service, '_docker_check', lambda: service._check('Docker', 'ok', '27.0.0'))

    result = service.validate(_request('upload-1', run_odm=True))

    assert result['ok'] is False
    assert '50.0 GB free; minimum 100 GB' in result['blockers']
    assert any(item['name'] == 'Free disk space' and item['state'] == 'error' for item in result['checks'])


def test_odm_preflight_warns_when_disk_space_is_near_minimum(tmp_path: Path, monkeypatch) -> None:
    storage = StorageService(project_root=tmp_path)
    upload_dir = storage.upload_dir('upload-1')
    storage.write_json(
        upload_dir / 'manifest.json',
        {'dataset_name': 'Dataset', 'rgb_files': ['a.jpg', 'b.jpg'], 'mapir_files': ['m1.jpg', 'm2.jpg']},
    )

    monkeypatch.setattr('agrivision.services.preflight_service.get_project_root', lambda: tmp_path)
    monkeypatch.setattr('agrivision.services.preflight_service.load_config', _config)
    monkeypatch.setattr(
        'agrivision.services.preflight_service.shutil.disk_usage',
        lambda path: shutil._ntuple_diskusage(total=200 * 1024**3, used=140 * 1024**3, free=60 * 1024**3),
    )
    service = PreflightService(storage)
    monkeypatch.setattr(service, '_docker_check', lambda: service._check('Docker', 'ok', '27.0.0'))

    result = service.validate(_request('upload-1', run_odm=True))

    assert result['ok'] is True
    assert any(item['name'] == 'Free disk space' and item['state'] == 'warn' for item in result['checks'])
