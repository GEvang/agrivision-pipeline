from __future__ import annotations

from copy import deepcopy

from PIL import Image

from agrivision.config.settings import DEFAULT_CONFIG
from agrivision.pipeline import orchestrator


def test_orchestrator_skip_path_runs_with_mocked_stages(monkeypatch, tmp_path):
    ortho_rgb = tmp_path / 'rgb.tif'
    vegetation_index = tmp_path / 'vegetation_index.tif'
    ortho_rgb.write_text('x', encoding='utf-8')
    vegetation_index.write_text('x', encoding='utf-8')

    monkeypatch.setattr(orchestrator, 'resolve_pipeline_paths', lambda **kwargs: {
        'config': {'location': {'name': 'Test Farm'}, 'irrigation': {'base_url': 'http://localhost:8004'}},
        'ortho_rgb': ortho_rgb,
        'ortho_mapir': tmp_path / 'missing_mapir.tif',
        'vegetation_index_output': tmp_path,
        'images_full_rgb': tmp_path / 'images_full_rgb',
        'images_full_mapir': tmp_path / 'images_full_mapir',
        'odm_project_root_rgb': tmp_path / 'odm_rgb',
        'odm_project_root_mapir': tmp_path / 'odm_mapir',
        'output_root': tmp_path / 'output',
        'report_path': tmp_path / 'output' / 'report_latest.html',
        'project_root': tmp_path,
    })
    monkeypatch.setattr(orchestrator, 'run_grid_report', lambda **kwargs: None)
    monkeypatch.setattr(orchestrator, 'run_report', lambda **kwargs: None)
    monkeypatch.setattr(orchestrator, 'run_weather_enrichment', lambda output_root, location_name: {'enabled': True, 'notes': []})
    monkeypatch.setattr(orchestrator, 'run_irrigation_enrichment', lambda base_url, **kwargs: {'enabled': True, 'authenticated': True, 'notes': []})
    monkeypatch.setattr(orchestrator, 'run_pdm_enrichment', lambda **kwargs: {'status': 'success', 'notes': []})

    orchestrator.run_full_pipeline(skip_odm=True, skip_vegetation_index=True)


def test_orchestrator_can_skip_irrigation(monkeypatch, tmp_path):
    ortho_rgb = tmp_path / 'rgb.tif'
    vegetation_index = tmp_path / 'vegetation_index.tif'
    ortho_rgb.write_text('x', encoding='utf-8')
    vegetation_index.write_text('x', encoding='utf-8')

    monkeypatch.setattr(orchestrator, 'resolve_pipeline_paths', lambda **kwargs: {
        'config': {'location': {'name': 'Test Farm'}, 'irrigation': {'base_url': 'http://localhost:8004'}},
        'ortho_rgb': ortho_rgb,
        'ortho_mapir': tmp_path / 'missing_mapir.tif',
        'vegetation_index_output': tmp_path,
        'images_full_rgb': tmp_path / 'images_full_rgb',
        'images_full_mapir': tmp_path / 'images_full_mapir',
        'odm_project_root_rgb': tmp_path / 'odm_rgb',
        'odm_project_root_mapir': tmp_path / 'odm_mapir',
        'output_root': tmp_path / 'output',
        'report_path': tmp_path / 'output' / 'report_latest.html',
        'project_root': tmp_path,
    })
    monkeypatch.setattr(orchestrator, 'run_grid_report', lambda **kwargs: None)
    monkeypatch.setattr(orchestrator, 'run_report', lambda **kwargs: None)
    monkeypatch.setattr(orchestrator, 'run_weather_enrichment', lambda output_root, location_name: {'enabled': True, 'notes': []})

    def fail_irrigation(base_url, **kwargs):
        raise AssertionError('irrigation should be skipped')

    monkeypatch.setattr(orchestrator, 'run_irrigation_enrichment', fail_irrigation)

    orchestrator.run_full_pipeline(skip_odm=True, skip_vegetation_index=True, skip_irrigation=True, skip_pdm=True)


def test_orchestrator_passes_run_scoped_integration_artifact_dirs(monkeypatch, tmp_path):
    ortho_rgb = tmp_path / 'rgb.tif'
    vegetation_index = tmp_path / 'vegetation_index.tif'
    ortho_rgb.write_text('x', encoding='utf-8')
    vegetation_index.write_text('x', encoding='utf-8')

    captured: dict[str, object] = {}
    output_root = tmp_path / 'workspace-output'
    monkeypatch.setattr(orchestrator, 'resolve_pipeline_paths', lambda **kwargs: {
        'config': {'location': {'name': 'Test Farm'}, 'irrigation': {'base_url': 'http://localhost:8004'}, 'pdm': {'base_url': 'http://localhost:8006'}},
        'ortho_rgb': ortho_rgb,
        'ortho_mapir': tmp_path / 'missing_mapir.tif',
        'vegetation_index_output': tmp_path,
        'images_full_rgb': tmp_path / 'images_full_rgb',
        'images_full_mapir': tmp_path / 'images_full_mapir',
        'odm_project_root_rgb': tmp_path / 'odm_rgb',
        'odm_project_root_mapir': tmp_path / 'odm_mapir',
        'output_root': output_root,
        'report_path': output_root / 'report_latest.html',
        'project_root': tmp_path,
    })
    monkeypatch.setattr(orchestrator, 'run_grid_report', lambda **kwargs: None)
    monkeypatch.setattr(orchestrator, 'run_report', lambda **kwargs: None)
    monkeypatch.setattr(orchestrator, 'run_weather_enrichment', lambda output_root, location_name: {'enabled': True, 'notes': []})

    def fake_irrigation(base_url, **kwargs):
        captured['irrigation_output_dir'] = kwargs.get('output_dir')
        return {'enabled': True, 'authenticated': True, 'notes': []}

    def fake_pdm(**kwargs):
        captured['pdm_artifact_dir'] = kwargs.get('artifact_dir')
        return {'status': 'success', 'notes': []}

    monkeypatch.setattr(orchestrator, 'run_irrigation_enrichment', fake_irrigation)
    monkeypatch.setattr(orchestrator, 'run_pdm_enrichment', fake_pdm)

    orchestrator.run_full_pipeline(skip_odm=True, skip_vegetation_index=True)

    assert captured['irrigation_output_dir'] == output_root / 'irrigation'
    assert captured['pdm_artifact_dir'] == output_root / 'pdm'


def test_orchestrator_falls_back_to_pixel_alignment_when_odm_fails(monkeypatch, tmp_path):
    config = deepcopy(DEFAULT_CONFIG)
    for rel in (
        config['paths']['images_full'],
        config['paths']['images_full_mapir'],
        config['paths']['images_full_thermal'],
    ):
        (tmp_path / rel).mkdir(parents=True, exist_ok=True)

    Image.new('RGB', (48, 48), color=(10, 180, 20)).save(tmp_path / config['paths']['images_full'] / 'rgb.png')
    Image.new('RGB', (40, 40), color=(60, 120, 200)).save(tmp_path / config['paths']['images_full_mapir'] / 'mapir.png')
    Image.new('L', (36, 36), color=150).save(tmp_path / config['paths']['images_full_thermal'] / 'thermal.png')

    monkeypatch.setattr(orchestrator, 'run_odm_rgb', lambda **kwargs: (_ for _ in ()).throw(RuntimeError('missing geotags')))
    monkeypatch.setattr(orchestrator, 'run_odm_mapir', lambda **kwargs: (_ for _ in ()).throw(RuntimeError('missing geotags')))
    monkeypatch.setattr(orchestrator, 'run_odm_thermal', lambda **kwargs: (_ for _ in ()).throw(RuntimeError('missing geotags')))

    orchestrator.run_full_pipeline(
        workspace_root=tmp_path,
        config=config,
        skip_weather=True,
        skip_irrigation=True,
        skip_pdm=True,
        skip_report=True,
    )

    assert (tmp_path / config['paths']['odm_project_root_rgb'] / 'project' / 'odm_orthophoto' / 'odm_orthophoto.tif').exists()
    assert (tmp_path / config['paths']['odm_project_root_mapir'] / 'project' / 'odm_orthophoto' / 'odm_orthophoto.tif').exists()
    assert (tmp_path / config['paths']['odm_project_root_thermal'] / 'project' / 'odm_orthophoto' / 'odm_orthophoto.tif').exists()
    assert (tmp_path / config['paths']['vegetation_index_output'] / 'vegetation_index.tif').exists()
    assert (tmp_path / config['paths']['vegetation_index_output'] / 'vegetation_index_grid_overlay.png').exists()
