from __future__ import annotations

from pathlib import Path

import rasterio
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import RedirectResponse
from PIL import Image, UnidentifiedImageError
from rasterio.errors import RasterioIOError

from agrivision.app import dependencies as deps
from agrivision.app.schemas.runs import RunCreateRequest, UploadManifest
from agrivision.config import load_config
from agrivision.services.run_service import RunStartBlocked

router = APIRouter()

ORTHOPHOTO_PRESET_VALUES = {
    'preview': {'resolution_cm': 8, 'reduce_images': False},
    'balanced': {'resolution_cm': 3, 'reduce_images': False},
    'high': {'resolution_cm': 2, 'reduce_images': False},
    'maximum': {'resolution_cm': 1, 'reduce_images': False},
}

CAMERA_KINDS = ('rgb', 'mapir', 'thermal')
ORTHOPHOTO_OUTPUT_KEYS = {
    'rgb': 'orthophoto_rgb',
    'mapir': 'orthophoto_mapir',
    'thermal': 'orthophoto_thermal',
}


async def _store_images(kind: str, uploads: list[UploadFile], target_dir: Path) -> tuple[list[str], list[str]]:
    seen_names: set[str] = set()
    stored_files: list[str] = []
    validation_errors: list[str] = []
    target_dir.mkdir(parents=True, exist_ok=True)
    for upload in uploads:
        name = Path(upload.filename or '').name
        if not name:
            continue
        suffix = Path(name).suffix.lower()
        if suffix not in deps.ALLOWED_EXTENSIONS:
            validation_errors.append(f'{kind} - {name}: unsupported file type')
            continue
        if name in seen_names:
            validation_errors.append(f'{kind} - {name}: duplicate or invalid name')
            continue
        seen_names.add(name)
        data = await upload.read()
        if not data:
            validation_errors.append(f'{kind} - {name}: empty file')
            continue
        target = target_dir / name
        target.write_bytes(data)
        try:
            with Image.open(target) as image:
                image.verify()
        except (UnidentifiedImageError, OSError):
            target.unlink(missing_ok=True)
            validation_errors.append(f'{kind} - {name}: unreadable or corrupt image')
            continue
        stored_files.append(name)
    return stored_files, validation_errors


def _validate_uploaded_categories(stored: dict[str, list[str]]) -> list[str]:
    errors: list[str] = []
    populated = {kind: files for kind, files in stored.items() if files}
    if not populated:
        return ['Upload at least one image category: RGB, MAPIR, or Thermal.']
    for kind, files in populated.items():
        if len(files) < deps.MINIMUM_DATASET_IMAGES:
            errors.append(f'{kind.upper()}: at least {deps.MINIMUM_DATASET_IMAGES} valid images are required.')
    return errors


def _manifest_payload(upload_run_id: str, dataset_name: str, upload_dir: Path, stored: dict[str, list[str]]) -> UploadManifest:
    return UploadManifest(
        run_id=upload_run_id,
        dataset_name=dataset_name,
        upload_dir=str(upload_dir),
        files=sorted(
            f'{kind}/{name}'
            for kind in CAMERA_KINDS
            for name in stored.get(kind, [])
        ),
        mapir_files=sorted(stored.get('mapir', [])),
        rgb_files=sorted(stored.get('rgb', [])),
        thermal_files=sorted(stored.get('thermal', [])),
        created_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc),
    )


@router.post('/uploads/images')
async def upload_images(
    dataset_name: str = Form(...),
    mapir_files: list[UploadFile] = File(default=[]),
    rgb_files: list[UploadFile] = File(default=[]),
    thermal_files: list[UploadFile] = File(default=[]),
) -> dict[str, object]:
    upload_run_id = deps.storage_service.new_run_id()
    upload_dir = deps.storage_service.upload_dir(upload_run_id)

    rgb_stored_files, rgb_errors = await _store_images('RGB', rgb_files, upload_dir / 'rgb')
    mapir_stored_files, mapir_errors = await _store_images('MAPIR', mapir_files, upload_dir / 'mapir')
    thermal_stored_files, thermal_errors = await _store_images('Thermal', thermal_files, upload_dir / 'thermal')
    stored = {'rgb': rgb_stored_files, 'mapir': mapir_stored_files, 'thermal': thermal_stored_files}
    errors = [*rgb_errors, *mapir_errors, *thermal_errors, *_validate_uploaded_categories(stored)]

    if errors:
        raise HTTPException(status_code=400, detail=errors)

    manifest = _manifest_payload(upload_run_id, dataset_name, upload_dir, stored)
    deps.storage_service.write_json(upload_dir / 'manifest.json', manifest.model_dump(mode='json'))
    return manifest.model_dump(mode='json')


@router.post('/ui/uploads')
async def upload_images_ui(
    dataset_name: str = Form(...),
    mapir_files: list[UploadFile] = File(default=[]),
    rgb_files: list[UploadFile] = File(default=[]),
    thermal_files: list[UploadFile] = File(default=[]),
) -> RedirectResponse:
    manifest = await upload_images(
        dataset_name=dataset_name,
        mapir_files=mapir_files,
        rgb_files=rgb_files,
        thermal_files=thermal_files,
    )
    return RedirectResponse(url=f"/runs/new?upload_run_id={manifest['run_id']}", status_code=303)


@router.post('/ui/orthophotos')
async def create_orthophotos_ui(
    dataset_name: str = Form(...),
    mapir_files: list[UploadFile] = File(default=[]),
    rgb_files: list[UploadFile] = File(default=[]),
    thermal_files: list[UploadFile] = File(default=[]),
    rgb_orthophoto: UploadFile | None = File(default=None),
    mapir_orthophoto: UploadFile | None = File(default=None),
    thermal_orthophoto: UploadFile | None = File(default=None),
    rgb_source: str = Form('raw'),
    mapir_source: str = Form('raw'),
    thermal_source: str = Form('raw'),
    orthophoto_preset: str = Form('balanced'),
    reduce_images: bool | None = Form(None),
) -> RedirectResponse:
    preset = ORTHOPHOTO_PRESET_VALUES.get(orthophoto_preset, ORTHOPHOTO_PRESET_VALUES['balanced'])
    source_modes = {
        'rgb': rgb_source if rgb_source in {'raw', 'ortho'} else 'raw',
        'mapir': mapir_source if mapir_source in {'raw', 'ortho'} else 'raw',
        'thermal': thermal_source if thermal_source in {'raw', 'ortho'} else 'raw',
    }
    raw_uploads = {
        'rgb': rgb_files if source_modes['rgb'] == 'raw' else [],
        'mapir': mapir_files if source_modes['mapir'] == 'raw' else [],
        'thermal': thermal_files if source_modes['thermal'] == 'raw' else [],
    }
    ortho_uploads = {
        'rgb': rgb_orthophoto if source_modes['rgb'] == 'ortho' else None,
        'mapir': mapir_orthophoto if source_modes['mapir'] == 'ortho' else None,
        'thermal': thermal_orthophoto if source_modes['thermal'] == 'ortho' else None,
    }

    upload_run_id = deps.storage_service.new_run_id()
    upload_dir = deps.storage_service.upload_dir(upload_run_id)
    rgb_stored_files, rgb_errors = await _store_images('RGB', raw_uploads['rgb'], upload_dir / 'rgb')
    mapir_stored_files, mapir_errors = await _store_images('MAPIR', raw_uploads['mapir'], upload_dir / 'mapir')
    thermal_stored_files, thermal_errors = await _store_images('Thermal', raw_uploads['thermal'], upload_dir / 'thermal')
    stored = {'rgb': rgb_stored_files, 'mapir': mapir_stored_files, 'thermal': thermal_stored_files}
    raw_errors = [*rgb_errors, *mapir_errors, *thermal_errors]
    for kind, files in stored.items():
        if raw_uploads[kind] and len(files) < deps.MINIMUM_DATASET_IMAGES:
            raw_errors.append(f'{kind.upper()}: at least {deps.MINIMUM_DATASET_IMAGES} valid images are required.')

    has_raw = any(stored[kind] for kind in CAMERA_KINDS)
    has_import = any(upload is not None and upload.filename for upload in ortho_uploads.values())
    if not has_raw and not has_import:
        raise HTTPException(status_code=400, detail='Choose raw images or a ready orthophoto for at least one camera.')
    if raw_errors:
        raise HTTPException(status_code=400, detail=raw_errors)

    manifest = _manifest_payload(upload_run_id, dataset_name, upload_dir, stored)
    deps.storage_service.write_json(upload_dir / 'manifest.json', manifest.model_dump(mode='json'))
    camera_targets = [
        kind
        for kind in CAMERA_KINDS
        if len(getattr(manifest, f'{kind}_files')) >= deps.MINIMUM_DATASET_IMAGES
    ]
    run_request = RunCreateRequest.model_validate(
        {
            'run_name': f'{manifest.dataset_name} orthophotos',
            'dataset_name': manifest.dataset_name,
            'upload_run_id': manifest.run_id,
            'selected_steps': {
                'resize_images': False,
                'run_odm': True,
                'fetch_weather': False,
                'run_irrigation': False,
                'run_pdm': False,
                'generate_report': False,
            },
            'parameters': {
                'orthophoto_preset': orthophoto_preset,
                'orthophoto_resolution_cm': preset['resolution_cm'],
                'camera_targets': camera_targets,
                'notes': 'Mixed ODM/import orthophoto intake' if has_import and has_raw else None,
            },
        }
    )
    record = deps.run_service.create_run_record(run_request)

    config = load_config()
    output_dir = (
        deps.storage_service.layout.project_root
        / config['paths'].get('runs_output', 'output/runs')
        / record.run_id
        / 'orthophotos'
    )
    import_errors: list[str] = []
    imported_outputs: dict[str, str] = {}
    for camera_kind, upload in ortho_uploads.items():
        path, camera_errors = await _store_imported_orthophoto(camera_kind, upload, output_dir)
        import_errors.extend(camera_errors)
        if path:
            imported_outputs[ORTHOPHOTO_OUTPUT_KEYS[camera_kind]] = path
    if import_errors:
        deps.run_service.update_status(
            record.run_id,
            status='failed',
            errors=import_errors,
            current_stage='import_orthophotos',
            stage_message='Imported orthophoto validation failed.',
        )
        raise HTTPException(status_code=400, detail=import_errors)
    if imported_outputs:
        deps.run_service.update_status(record.run_id, outputs=imported_outputs)

    if not camera_targets:
        completed = deps.run_service.update_status(
            record.run_id,
            status='completed',
            outputs=imported_outputs,
            progress_percent=100,
            current_stage='completed',
            stage_message='Premade orthophotos imported.',
            started_at=record.created_at,
            finished_at=record.created_at,
        )
        return RedirectResponse(url=f'/runs/{completed.run_id}', status_code=303)

    try:
        result = deps.run_service.start_run(record.run_id)
    except RunStartBlocked as exc:
        result = deps.run_service.mark_start_blocked(record.run_id, str(exc))
    return RedirectResponse(url=f'/runs/{result.run_id}', status_code=303)


@router.post('/ui/orthophotos/{run_id}/upload/{camera_kind}')
async def upload_missing_orthophoto_camera_ui(
    run_id: str,
    camera_kind: str,
    files: list[UploadFile] = File(default=[]),
    orthophoto_preset: str = Form('balanced'),
) -> RedirectResponse:
    if camera_kind not in {'rgb', 'mapir', 'thermal'}:
        raise HTTPException(status_code=404, detail='Camera category not found.')
    source_run = deps.run_service.load_run(run_id)
    upload_run_id = Path(source_run.input_path).name
    upload_dir = deps.storage_service.upload_dir(upload_run_id)
    manifest = deps.storage_service.read_json(upload_dir / 'manifest.json', default={})
    dataset_name = str(manifest.get('dataset_name') or source_run.dataset_name)
    stored_files, errors = await _store_images(camera_kind.upper(), files, upload_dir / camera_kind)
    if len(stored_files) < deps.MINIMUM_DATASET_IMAGES:
        errors.append(f'{camera_kind.upper()}: at least {deps.MINIMUM_DATASET_IMAGES} valid images are required.')
    if errors:
        raise HTTPException(status_code=400, detail=errors)

    existing = {
        'rgb': list(manifest.get('rgb_files', [])),
        'mapir': list(manifest.get('mapir_files', [])),
        'thermal': list(manifest.get('thermal_files', [])),
    }
    existing[camera_kind] = sorted(set(existing.get(camera_kind, [])) | set(stored_files))
    updated_manifest = _manifest_payload(upload_run_id, dataset_name, upload_dir, existing)
    deps.storage_service.write_json(upload_dir / 'manifest.json', updated_manifest.model_dump(mode='json'))

    preset = ORTHOPHOTO_PRESET_VALUES.get(orthophoto_preset, ORTHOPHOTO_PRESET_VALUES['balanced'])
    run_request = RunCreateRequest.model_validate(
        {
            'run_name': f'{dataset_name} {camera_kind.upper()} orthophoto',
            'dataset_name': dataset_name,
            'upload_run_id': upload_run_id,
            'selected_steps': {
                'resize_images': False,
                'run_odm': True,
                'fetch_weather': False,
                'run_irrigation': False,
                'run_pdm': False,
                'generate_report': False,
            },
            'parameters': {
                'orthophoto_preset': orthophoto_preset,
                'orthophoto_resolution_cm': preset['resolution_cm'],
                'camera_targets': [camera_kind],
            },
        }
    )
    record = deps.run_service.create_run_record(run_request)
    try:
        result = deps.run_service.start_run(record.run_id)
    except RunStartBlocked as exc:
        result = deps.run_service.mark_start_blocked(record.run_id, str(exc))
    return RedirectResponse(url=f'/runs/{result.run_id}', status_code=303)


async def _store_imported_orthophoto(camera_kind: str, upload: UploadFile | None, target_dir: Path) -> tuple[str | None, list[str]]:
    if upload is None or not upload.filename:
        return None, []
    name = Path(upload.filename).name
    suffix = Path(name).suffix.lower()
    if suffix not in {'.tif', '.tiff'}:
        return None, [f'{camera_kind.upper()} orthophoto must be a GeoTIFF (.tif or .tiff).']
    data = await upload.read()
    if not data:
        return None, [f'{camera_kind.upper()} orthophoto file is empty.']
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f'orthophoto_{camera_kind}.tif'
    target.write_bytes(data)
    try:
        with rasterio.open(target) as dataset:
            if dataset.width <= 0 or dataset.height <= 0:
                raise ValueError('invalid raster dimensions')
            if dataset.crs is None:
                raise ValueError('missing CRS')
            if dataset.transform.is_identity:
                raise ValueError('missing geotransform')
    except (RasterioIOError, ValueError) as exc:
        target.unlink(missing_ok=True)
        return None, [f'{camera_kind.upper()} orthophoto is not a valid georeferenced GeoTIFF: {exc}']
    return str(target), []


@router.post('/ui/orthophotos/import')
async def import_orthophotos_ui(
    dataset_name: str = Form(...),
    rgb_orthophoto: UploadFile | None = File(default=None),
    mapir_orthophoto: UploadFile | None = File(default=None),
    thermal_orthophoto: UploadFile | None = File(default=None),
) -> RedirectResponse:
    uploads = {
        'rgb': rgb_orthophoto,
        'mapir': mapir_orthophoto,
        'thermal': thermal_orthophoto,
    }
    if not any(upload is not None and upload.filename for upload in uploads.values()):
        raise HTTPException(status_code=400, detail='Upload at least one premade orthophoto.')

    upload_run_id = deps.storage_service.new_run_id()
    upload_dir = deps.storage_service.upload_dir(upload_run_id)
    manifest = _manifest_payload(upload_run_id, dataset_name, upload_dir, {'rgb': [], 'mapir': [], 'thermal': []})
    deps.storage_service.write_json(upload_dir / 'manifest.json', manifest.model_dump(mode='json'))

    run_request = RunCreateRequest.model_validate(
        {
            'run_name': f'{dataset_name} imported orthophotos',
            'dataset_name': dataset_name,
            'upload_run_id': upload_run_id,
            'selected_steps': {
                'resize_images': False,
                'run_odm': False,
                'fetch_weather': False,
                'run_irrigation': False,
                'run_pdm': False,
                'generate_report': False,
            },
            'parameters': {
                'orthophoto_preset': 'imported',
                'source_orthophoto_run_id': None,
                'camera_targets': [kind for kind, upload in uploads.items() if upload is not None and upload.filename],
                'notes': 'Imported premade orthophotos',
            },
        }
    )
    record = deps.run_service.create_run_record(run_request)
    config = load_config()
    output_dir = (
        deps.storage_service.layout.project_root
        / config['paths'].get('runs_output', 'output/runs')
        / record.run_id
        / 'orthophotos'
    )
    errors: list[str] = []
    outputs: dict[str, str] = {}
    for camera_kind, upload in uploads.items():
        path, camera_errors = await _store_imported_orthophoto(camera_kind, upload, output_dir)
        errors.extend(camera_errors)
        if path:
            outputs[ORTHOPHOTO_OUTPUT_KEYS[camera_kind]] = path
    if errors:
        deps.run_service.update_status(
            record.run_id,
            status='failed',
            errors=errors,
            current_stage='import_orthophotos',
            stage_message='Imported orthophoto validation failed.',
        )
        raise HTTPException(status_code=400, detail=errors)

    completed = deps.run_service.update_status(
        record.run_id,
        status='completed',
        outputs=outputs,
        progress_percent=100,
        current_stage='completed',
        stage_message='Premade orthophotos imported.',
        started_at=record.created_at,
        finished_at=record.created_at,
    )
    return RedirectResponse(url=f'/runs/{completed.run_id}', status_code=303)
