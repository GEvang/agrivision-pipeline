from __future__ import annotations

from pathlib import Path
from typing import Callable

from agrivision.pipeline.io.paths import resolve_pipeline_paths
from agrivision.pipeline.stages.grid import run_grid_report
from agrivision.pipeline.stages.irrigation_enrichment import run_irrigation_enrichment
from agrivision.pipeline.stages.odm import run_odm_mapir, run_odm_rgb
from agrivision.pipeline.stages.pdm_enrichment import run_pdm_enrichment
from agrivision.pipeline.stages.report import run_report
from agrivision.pipeline.stages.resize import run_resize
from agrivision.pipeline.stages.vegetation_index import run_ndvi
from agrivision.pipeline.stages.weather_enrichment import run_weather_enrichment
from agrivision.pipeline.state import folder_has_images


def _orthophoto_exists(path: Path) -> bool:
    return path.exists()


def _ndvi_exists(path: Path) -> bool:
    return path.exists()


def run_full_pipeline(
    run_resize_step: bool = False,
    skip_odm: bool = False,
    skip_odm_rgb: bool = False,
    skip_odm_mapir: bool = False,
    skip_ndvi: bool = False,
    skip_grid: bool = False,
    skip_weather: bool = False,
    skip_irrigation: bool = False,
    skip_pdm: bool = False,
    skip_report: bool = False,
    orthophoto_resolution_cm: int | None = None,
    pdm_crop: str | None = None,
    pdm_model_key: str | None = None,
    progress_callback: Callable[[str, str, str], None] | None = None,
) -> None:
    print("\n================== AgriVision Pipeline Start ==================\n")
    print("Configuration:")
    print(f"  run_resize_step = {run_resize_step}")
    print(f"  skip_odm        = {skip_odm}")
    print(f"  skip_odm_rgb    = {skip_odm_rgb}")
    print(f"  skip_odm_mapir  = {skip_odm_mapir}")
    print(f"  skip_ndvi       = {skip_ndvi}")
    print(f"  skip_grid       = {skip_grid}")
    print(f"  skip_weather    = {skip_weather}")
    print(f"  skip_irrigation = {skip_irrigation}")
    print(f"  skip_pdm        = {skip_pdm}")
    print(f"  skip_report     = {skip_report}")
    print()

    resolved = resolve_pipeline_paths()
    config = resolved['config']
    ortho_rgb = resolved['ortho_rgb']
    ortho_mapir = resolved['ortho_mapir']
    ndvi_tif = resolved['ndvi_output'] / 'ndvi.tif'
    images_full_mapir = resolved['images_full_mapir']
    images_resized_mapir = resolved['images_resized_mapir']
    output_root = resolved['output_root']

    if run_resize_step:
        if progress_callback:
            progress_callback('resize_images', 'Resizing images', 'running')
        print('Step 1/5: Resizing images...')
        run_resize()
        if progress_callback:
            progress_callback('resize_images', 'Images resized', 'completed')
    else:
        print('Step 1/5: Skipping resize (no --run-resize flag).')
        print('          ODM will auto-select full vs resized images.')

    if skip_odm:
        skip_odm_rgb = True
        skip_odm_mapir = True
        print('\nStep 2/5: Skipping ODM (--skip-odm).')

    if skip_odm_rgb:
        print('\n[ODM-RGB] Skipping RGB ODM step.')
        if _orthophoto_exists(ortho_rgb):
            print(f'[ODM-RGB] Reusing existing RGB orthophoto: {ortho_rgb}')
        else:
            print(f'[ODM-RGB] No existing RGB orthophoto found at: {ortho_rgb}')
    else:
        if progress_callback:
            progress_callback('run_odm_rgb', 'Running ODM for RGB images', 'running')
        print('\n[ODM-RGB] Running RGB ODM...')
        run_odm_rgb(ortho_resolution_cm=orthophoto_resolution_cm)
        if progress_callback:
            progress_callback('run_odm_rgb', 'RGB orthophoto complete', 'completed')

    if skip_odm_mapir:
        print('\n[ODM-MAPIR] Skipping MAPIR ODM (skip flag active).')
    else:
        if folder_has_images(images_full_mapir) or folder_has_images(images_resized_mapir):
            if progress_callback:
                progress_callback('run_odm_mapir', 'Running ODM for MAPIR images', 'running')
            print('\n[ODM-MAPIR] MAPIR images detected – running MAPIR ODM...')
            run_odm_mapir(ortho_resolution_cm=orthophoto_resolution_cm)
            if progress_callback:
                progress_callback('run_odm_mapir', 'MAPIR orthophoto complete', 'completed')
        else:
            print('\n[ODM-MAPIR] No MAPIR images found. Skipping MAPIR ODM.')
            if progress_callback:
                progress_callback('run_odm_mapir', 'No MAPIR images found', 'completed')

    if skip_ndvi:
        print('\nStep 3/5: Skipping NDVI (--skip-ndvi).')
        if not skip_grid and not _ndvi_exists(ndvi_tif):
            raise RuntimeError(
                f'\n[ERROR] NDVI skipped but NDVI output missing:\n  {ndvi_tif}\n'
            )
    else:
        if progress_callback:
            progress_callback('compute_ndvi', 'Computing NDVI', 'running')
        print('\nStep 3/5: Computing NDVI...')
        if not _orthophoto_exists(ortho_rgb) and not _orthophoto_exists(ortho_mapir):
            raise RuntimeError('\n[ERROR] No orthophoto available for NDVI.\n')
        run_ndvi()
        if progress_callback:
            progress_callback('compute_ndvi', 'NDVI complete', 'completed')

    if skip_grid:
        print('\nStep 4/5: Skipping NDVI grid (--skip-grid).')
    else:
        if progress_callback:
            progress_callback('generate_grid', 'Generating NDVI grid', 'running')
        print('\nStep 4/5: Generating NDVI grid...')
        run_grid_report()
        if progress_callback:
            progress_callback('generate_grid', 'NDVI grid complete', 'completed')

    if skip_weather:
        print('\n[AgriVision] Skipping Weather integration (--skip-weather).')
        weather_summary = {'enabled': False, 'notes': ['Skipped by configuration.']}
    else:
        if progress_callback:
            progress_callback('fetch_weather', 'Fetching weather data', 'running')
        print('\n[AgriVision] Running Weather integration ...')
        weather_summary = run_weather_enrichment(
            output_root, config.get('location', {}).get('name', 'Unknown location')
        )
        if weather_summary.get('enabled'):
            print('[AgriVision] ✅ Weather integration completed')
        else:
            print('[AgriVision] ⚠️ Weather integration failed (continuing pipeline).')
            print(f"[AgriVision] Reason: {weather_summary.get('notes', [''])[0]}")
        if progress_callback:
            progress_callback('fetch_weather', 'Weather enrichment complete', 'completed')

    if skip_irrigation:
        print('\n[AgriVision] Skipping Irrigation integration (--skip-irrigation).')
        irrigation_summary = {'enabled': False, 'notes': ['Skipped by configuration.']}
    else:
        if progress_callback:
            progress_callback('irrigation_enrichment', 'Running irrigation enrichment', 'running')
        print('\n[AgriVision] Running Irrigation integration (config-driven ETo) ...')
        irrigation_summary = run_irrigation_enrichment(
            config.get('irrigation', {}).get('base_url', '')
        )
        if irrigation_summary.get('authenticated') or irrigation_summary.get('enabled'):
            print('[AgriVision] Irrigation integration completed')
        else:
            print('[AgriVision] Irrigation integration failed (continuing pipeline).')
            print(f"[AgriVision] Reason: {irrigation_summary.get('notes', [''])[0]}")
        if progress_callback:
            progress_callback('irrigation_enrichment', 'Irrigation enrichment complete', 'completed')

    pdm_cfg = config.get('pdm', {}) if isinstance(config.get('pdm'), dict) else {}
    resolved_pdm_crop = (pdm_crop or pdm_cfg.get('default_crop') or 'grapevine')
    resolved_pdm_model_key = (pdm_model_key or pdm_cfg.get('default_model_key') or 'grapevine_powdery_mildew_risk_v1')
    if skip_pdm:
        print('\n[AgriVision] Skipping PDM integration (--skip-pdm).')
        pdm_summary = {'enabled': False, 'status': 'disabled', 'notes': ['Skipped by configuration.']}
    else:
        if progress_callback:
            progress_callback('pdm_enrichment', 'Running pest & disease enrichment', 'running')
        print('\n[AgriVision] Running Pest & Disease integration ...')
        pdm_summary = run_pdm_enrichment(
            base_url=pdm_cfg.get('base_url', ''),
            weather_summary=weather_summary,
            enabled=True,
            crop=resolved_pdm_crop,
            model_key=resolved_pdm_model_key,
        )
        if pdm_summary.get('status') == 'success':
            print('[AgriVision] ✅ Pest & Disease integration completed')
        else:
            print('[AgriVision] ⚠️ Pest & Disease integration failed or degraded (continuing pipeline).')
            print(f"[AgriVision] Reason: {pdm_summary.get('error_message') or (pdm_summary.get('notes', [''])[0] if pdm_summary.get('notes') else '')}")
        if progress_callback:
            progress_callback('pdm_enrichment', 'Pest & disease enrichment complete', 'completed')

    if skip_report:
        print('\nStep 5/5: Skipping report generation (--skip-report).')
    else:
        if progress_callback:
            progress_callback('generate_report', 'Generating report', 'running')
        print('\nStep 5/5: Creating report...')
        run_report(irrigation_summary=irrigation_summary, weather_summary=weather_summary, pdm_summary=pdm_summary)
        if progress_callback:
            progress_callback('generate_report', 'Report generated', 'completed')
    print('\n================== Pipeline Complete ==================\n')
