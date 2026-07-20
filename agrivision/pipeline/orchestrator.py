from __future__ import annotations

from pathlib import Path
from typing import Callable

from agrivision.pipeline.io.paths import resolve_pipeline_paths
from agrivision.pipeline.stages.disease_risk import run_disease_risk
from agrivision.pipeline.stages.grid import run_grid_report
from agrivision.pipeline.stages.irrigation_enrichment import run_irrigation_enrichment
from agrivision.pipeline.stages.odm import run_odm_mapir, run_odm_rgb, run_odm_thermal
from agrivision.pipeline.stages.pdm_enrichment import run_pdm_enrichment
from agrivision.pipeline.stages.pixel_alignment import run_pixel_alignment_fallback
from agrivision.pipeline.stages.report import run_report
from agrivision.pipeline.stages.vegetation_index import run_vegetation_index
from agrivision.pipeline.stages.weather_enrichment import run_weather_enrichment
from agrivision.pipeline.state import folder_has_images


def _orthophoto_exists(path: Path) -> bool:
    return path.exists()


def _vegetation_index_exists(path: Path) -> bool:
    return path.exists()


def run_full_pipeline(
    skip_odm: bool = False,
    skip_odm_rgb: bool = False,
    skip_odm_mapir: bool = False,
    skip_odm_thermal: bool = False,
    skip_vegetation_index: bool = False,
    skip_grid: bool = False,
    skip_weather: bool = False,
    skip_irrigation: bool = False,
    skip_pdm: bool = False,
    skip_report: bool = False,
    orthophoto_resolution_cm: int | None = None,
    pdm_crop: str | None = None,
    pdm_model_key: str | None = None,
    progress_callback: Callable[[str, str, str], None] | None = None,
    workspace_root: Path | None = None,
    config: dict | None = None,
) -> None:
    print("\n================== AgriVision Pipeline Start ==================\n")
    print("Configuration:")
    print(f"  skip_odm        = {skip_odm}")
    print(f"  skip_odm_rgb    = {skip_odm_rgb}")
    print(f"  skip_odm_mapir  = {skip_odm_mapir}")
    print(f"  skip_odm_thermal= {skip_odm_thermal}")
    print(f"  skip_vegetation_index       = {skip_vegetation_index}")
    print(f"  skip_grid       = {skip_grid}")
    print(f"  skip_weather    = {skip_weather}")
    print(f"  skip_irrigation = {skip_irrigation}")
    print(f"  skip_pdm        = {skip_pdm}")
    print(f"  skip_report     = {skip_report}")
    print()

    resolved = resolve_pipeline_paths(workspace_root=workspace_root, config=config)
    config = resolved['config']
    ortho_rgb = resolved['ortho_rgb']
    ortho_mapir = resolved['ortho_mapir']
    ortho_thermal = resolved.get('ortho_thermal')
    vegetation_index_tif = resolved['vegetation_index_output'] / 'vegetation_index.tif'
    images_full_rgb = resolved.get('images_full_rgb')
    images_full_mapir = resolved.get('images_full_mapir')
    images_full_thermal = resolved.get('images_full_thermal')
    output_root = resolved['output_root']
    pixel_fallback_used = False
    odm_failures: list[str] = []

    def _available_demo_inputs() -> bool:
        return any(
            isinstance(path, Path) and folder_has_images(path)
            for path in (images_full_rgb, images_full_mapir, images_full_thermal)
        )

    def _run_pixel_fallback(reason: str) -> None:
        nonlocal pixel_fallback_used
        if pixel_fallback_used:
            return
        if not _available_demo_inputs():
            raise RuntimeError(reason)
        if progress_callback:
            progress_callback('run_odm_rgb', 'Falling back to pixel-space demo alignment', 'running')
        print(f"\n[Demo Alignment] {reason}")
        run_pixel_alignment_fallback(workspace_root=workspace_root, config=config)
        pixel_fallback_used = True
        if progress_callback:
            for stage_key, label in (
                ('run_odm_rgb', 'RGB fallback analysis image ready'),
                ('run_odm_mapir', 'MAPIR fallback analysis image ready'),
                ('run_odm_thermal', 'Thermal fallback analysis image ready'),
            ):
                progress_callback(stage_key, label, 'completed')

    print('Step 1/5: ODM will use full-resolution images.')

    if skip_odm:
        skip_odm_rgb = True
        skip_odm_mapir = True
        skip_odm_thermal = True
        print('\nStep 2/5: Skipping ODM (--skip-odm).')

    if skip_odm_rgb:
        print('\n[ODM-RGB] Skipping RGB ODM step.')
        if _orthophoto_exists(ortho_rgb):
            print(f'[ODM-RGB] Reusing existing RGB orthophoto: {ortho_rgb}')
        else:
            print(f'[ODM-RGB] No existing RGB orthophoto found at: {ortho_rgb}')
    else:
        if isinstance(images_full_rgb, Path) and folder_has_images(images_full_rgb):
            if progress_callback:
                progress_callback('run_odm_rgb', 'Running ODM for RGB images', 'running')
            print('\n[ODM-RGB] Running RGB ODM...')
            try:
                run_odm_rgb(ortho_resolution_cm=orthophoto_resolution_cm, workspace_root=workspace_root, config=config)
                if progress_callback:
                    progress_callback('run_odm_rgb', 'RGB orthophoto complete', 'completed')
            except Exception as exc:
                message = f'RGB ODM failed ({exc}); using pixel-space demo fallback instead.'
                odm_failures.append(message)
                _run_pixel_fallback(message)
        else:
            print('\n[ODM-RGB] No RGB images found. Skipping RGB ODM.')
            if progress_callback:
                progress_callback('run_odm_rgb', 'No RGB images found', 'completed')

    if skip_odm_mapir:
        print('\n[ODM-MAPIR] Skipping MAPIR ODM (skip flag active).')
    else:
        if pixel_fallback_used:
            print('\n[ODM-MAPIR] Demo fallback already created MAPIR analysis image.')
        elif isinstance(images_full_mapir, Path) and folder_has_images(images_full_mapir):
            if progress_callback:
                progress_callback('run_odm_mapir', 'Running ODM for MAPIR images', 'running')
            print('\n[ODM-MAPIR] MAPIR images detected â€“ running MAPIR ODM...')
            try:
                run_odm_mapir(ortho_resolution_cm=orthophoto_resolution_cm, workspace_root=workspace_root, config=config)
                if progress_callback:
                    progress_callback('run_odm_mapir', 'MAPIR orthophoto complete', 'completed')
            except Exception as exc:
                message = f'MAPIR ODM failed ({exc}); using pixel-space demo fallback instead.'
                odm_failures.append(message)
                _run_pixel_fallback(message)
        else:
            print('\n[ODM-MAPIR] No MAPIR images found. Skipping MAPIR ODM.')
            if progress_callback:
                progress_callback('run_odm_mapir', 'No MAPIR images found', 'completed')

    if skip_odm_thermal:
        print('\n[ODM-THERMAL] Skipping thermal ODM (skip flag active).')
        if isinstance(ortho_thermal, Path) and _orthophoto_exists(ortho_thermal):
            print(f'[ODM-THERMAL] Reusing existing thermal orthophoto: {ortho_thermal}')
    else:
        if pixel_fallback_used:
            print('\n[ODM-THERMAL] Demo fallback already created thermal analysis image.')
        elif isinstance(images_full_thermal, Path) and folder_has_images(images_full_thermal):
            if progress_callback:
                progress_callback('run_odm_thermal', 'Running ODM for thermal images', 'running')
            print('\n[ODM-THERMAL] Thermal images detected - running thermal ODM...')
            try:
                run_odm_thermal(ortho_resolution_cm=orthophoto_resolution_cm, workspace_root=workspace_root, config=config)
                if progress_callback:
                    progress_callback('run_odm_thermal', 'Thermal orthophoto complete', 'completed')
            except Exception as exc:
                message = f'Thermal ODM failed ({exc}); using pixel-space demo fallback instead.'
                odm_failures.append(message)
                _run_pixel_fallback(message)
        else:
            print('\n[ODM-THERMAL] No thermal images found. Skipping thermal ODM.')
            if progress_callback:
                progress_callback('run_odm_thermal', 'No thermal images found', 'completed')

    if not _orthophoto_exists(ortho_rgb) and not _orthophoto_exists(ortho_mapir) and _available_demo_inputs():
        _run_pixel_fallback('No orthophoto outputs were generated; using pixel-space demo fallback.')
    elif odm_failures and not pixel_fallback_used:
        raise RuntimeError(odm_failures[0])

    if skip_vegetation_index:
        print('\nStep 3/5: Skipping Vegetation Index (--skip-vegetation-index).')
        if not skip_grid and not _vegetation_index_exists(vegetation_index_tif):
            raise RuntimeError(
                f'\n[ERROR] Vegetation Index skipped but Vegetation Index output missing:\n  {vegetation_index_tif}\n'
            )
    else:
        if progress_callback:
            progress_callback('compute_vegetation_index', 'Computing Vegetation Index', 'running')
        print('\nStep 3/5: Computing Vegetation Index...')
        if not _orthophoto_exists(ortho_rgb) and not _orthophoto_exists(ortho_mapir):
            raise RuntimeError('\n[ERROR] No orthophoto available for Vegetation Index.\n')
        run_vegetation_index(workspace_root=workspace_root, config=config)
        if progress_callback:
            progress_callback('compute_vegetation_index', 'Vegetation Index complete', 'completed')

    if skip_grid:
        print('\nStep 4/5: Skipping Vegetation Index grid (--skip-grid).')
    else:
        if progress_callback:
            progress_callback('generate_grid', 'Generating Vegetation Index grid', 'running')
        print('\nStep 4/5: Generating Vegetation Index grid...')
        run_grid_report(workspace_root=workspace_root, config=config)
        if progress_callback:
            progress_callback('generate_grid', 'Vegetation Index grid complete', 'completed')

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
            print('[AgriVision] âœ… Weather integration completed')
        else:
            print('[AgriVision] âš ï¸ Weather integration failed (continuing pipeline).')
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
            config.get('irrigation', {}).get('base_url', ''),
            output_dir=output_root / 'irrigation',
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
            artifact_dir=output_root / 'pdm',
        )
        if pdm_summary.get('status') == 'success':
            print('[AgriVision] âœ… Pest & Disease integration completed')
        else:
            print('[AgriVision] âš ï¸ Pest & Disease integration failed or degraded (continuing pipeline).')
            print(f"[AgriVision] Reason: {pdm_summary.get('error_message') or (pdm_summary.get('notes', [''])[0] if pdm_summary.get('notes') else '')}")
        if progress_callback:
            progress_callback('pdm_enrichment', 'Pest & disease enrichment complete', 'completed')

    disease_risk_summary = {'enabled': False, 'notes': ['Disease risk scoring skipped.']}
    if not skip_grid:
        if progress_callback:
            progress_callback('disease_risk', 'Scoring disease risk layers', 'running')
        try:
            disease_risk_summary = run_disease_risk(
                crop=resolved_pdm_crop,
                weather_summary=weather_summary,
                irrigation_summary=irrigation_summary,
            )
        except Exception as exc:
            disease_risk_summary = {
                'enabled': False,
                'status': 'failed',
                'error_message': str(exc),
                'notes': ['Disease risk scoring failed; report will use the standard grid overlay.'],
            }
            print(f'[AgriVision] Disease risk scoring failed (continuing pipeline): {exc}')
        if progress_callback:
            progress_callback('disease_risk', 'Disease risk scoring complete', 'completed')

    if skip_report:
        print('\nStep 5/5: Skipping report generation (--skip-report).')
    else:
        if progress_callback:
            progress_callback('generate_report', 'Generating report', 'running')
        print('\nStep 5/5: Creating report...')
        run_report(
            irrigation_summary=irrigation_summary,
            weather_summary=weather_summary,
            pdm_summary=pdm_summary,
            workspace_root=workspace_root,
            config=config,
            disease_risk_summary=disease_risk_summary,
        )
        if progress_callback:
            progress_callback('generate_report', 'Report generated', 'completed')
    print('\n================== Pipeline Complete ==================\n')
