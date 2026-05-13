from __future__ import annotations

from agrivision.pipeline import orchestrator


def test_orchestrator_skip_path_runs_with_mocked_stages(monkeypatch, tmp_path):
    ortho_rgb = tmp_path / 'rgb.tif'
    ndvi = tmp_path / 'ndvi.tif'
    ortho_rgb.write_text('x', encoding='utf-8')
    ndvi.write_text('x', encoding='utf-8')

    monkeypatch.setattr(orchestrator, 'resolve_pipeline_paths', lambda: {
        'config': {'location': {'name': 'Test Farm'}, 'irrigation': {'base_url': 'http://localhost:8004'}},
        'ortho_rgb': ortho_rgb,
        'ortho_mapir': tmp_path / 'missing_mapir.tif',
        'ndvi_output': tmp_path,
        'images_full_mapir': tmp_path / 'images_full_mapir',
        'images_resized_mapir': tmp_path / 'images_resized_mapir',
        'output_root': tmp_path / 'output',
    })
    monkeypatch.setattr(orchestrator, 'run_grid_report', lambda: None)
    monkeypatch.setattr(orchestrator, 'run_report', lambda **kwargs: None)
    monkeypatch.setattr(orchestrator, 'run_weather_enrichment', lambda output_root, location_name: {'enabled': True, 'notes': []})
    monkeypatch.setattr(orchestrator, 'run_irrigation_enrichment', lambda base_url: {'enabled': True, 'authenticated': True, 'notes': []})

    orchestrator.run_full_pipeline(skip_odm=True, skip_ndvi=True)


def test_orchestrator_can_skip_irrigation(monkeypatch, tmp_path):
    ortho_rgb = tmp_path / 'rgb.tif'
    ndvi = tmp_path / 'ndvi.tif'
    ortho_rgb.write_text('x', encoding='utf-8')
    ndvi.write_text('x', encoding='utf-8')

    monkeypatch.setattr(orchestrator, 'resolve_pipeline_paths', lambda: {
        'config': {'location': {'name': 'Test Farm'}, 'irrigation': {'base_url': 'http://localhost:8004'}},
        'ortho_rgb': ortho_rgb,
        'ortho_mapir': tmp_path / 'missing_mapir.tif',
        'ndvi_output': tmp_path,
        'images_full_mapir': tmp_path / 'images_full_mapir',
        'images_resized_mapir': tmp_path / 'images_resized_mapir',
        'output_root': tmp_path / 'output',
    })
    monkeypatch.setattr(orchestrator, 'run_grid_report', lambda: None)
    monkeypatch.setattr(orchestrator, 'run_report', lambda **kwargs: None)
    monkeypatch.setattr(orchestrator, 'run_weather_enrichment', lambda output_root, location_name: {'enabled': True, 'notes': []})

    def fail_irrigation(base_url):
        raise AssertionError('irrigation should be skipped')

    monkeypatch.setattr(orchestrator, 'run_irrigation_enrichment', fail_irrigation)

    orchestrator.run_full_pipeline(skip_odm=True, skip_ndvi=True, skip_irrigation=True, skip_pdm=True)
