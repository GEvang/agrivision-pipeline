from __future__ import annotations

import shutil
import warnings
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import RedirectResponse
from PIL import Image, UnidentifiedImageError

from agrivision.app import dependencies as deps
from agrivision.app.schemas.runs import RunCreateRequest, UploadManifest
from agrivision.services.run_service import RunStartBlocked

router = APIRouter()

UPLOAD_STREAM_CHUNK_SIZE = 1024 * 1024
MAX_FILES_PER_GROUP = 1000
MAX_DATASET_BYTES = 2 * 1024 * 1024 * 1024
MAX_IMAGE_PIXELS = 100_000_000

ORTHOPHOTO_PRESET_VALUES = {
    'preview': {'resolution_cm': 8, 'reduce_images': True},
    'balanced': {'resolution_cm': 3, 'reduce_images': True},
    'high': {'resolution_cm': 2, 'reduce_images': False},
    'maximum': {'resolution_cm': 1, 'reduce_images': False},
}


@router.post('/uploads/images')
async def upload_images(
    dataset_name: str = Form(...),
    mapir_files: list[UploadFile] = File(...),
    rgb_files: list[UploadFile] = File(...),
) -> dict[str, object]:
    upload_run_id = deps.storage_service.new_run_id()
    upload_dir = deps.storage_service.upload_dir(upload_run_id)
    mapir_dir = upload_dir / 'mapir'
    rgb_dir = upload_dir / 'rgb'
    mapir_dir.mkdir(parents=True, exist_ok=True)
    rgb_dir.mkdir(parents=True, exist_ok=True)
    total_bytes = 0
    seen_names: set[str] = set()

    async def _store_images(kind: str, uploads: list[UploadFile], target_dir: Path) -> tuple[list[str], list[str]]:
        stored_files: list[str] = []
        validation_errors: list[str] = []
        nonlocal total_bytes
        if len(uploads) > MAX_FILES_PER_GROUP:
            validation_errors.append(f'{kind}: no more than {MAX_FILES_PER_GROUP} files are allowed.')
            return stored_files, validation_errors
        for upload in uploads:
            try:
                suffix = Path(upload.filename or '').suffix.lower()
                name = Path(upload.filename or '').name
                if suffix not in deps.ALLOWED_EXTENSIONS:
                    validation_errors.append(f'{kind} - {name}: unsupported file type')
                    continue
                if not name or name in seen_names:
                    validation_errors.append(f'{kind} - {name or "<unnamed>"}: duplicate or invalid name')
                    continue
                seen_names.add(name)
                target = target_dir / name
                temp_target = target_dir / f'{name}.tmp'
                file_size = 0
                while True:
                    chunk = await upload.read(UPLOAD_STREAM_CHUNK_SIZE)
                    if not chunk:
                        break
                    file_size += len(chunk)
                    total_bytes += len(chunk)
                    if total_bytes > MAX_DATASET_BYTES:
                        raise ValueError(f'dataset exceeds the {MAX_DATASET_BYTES} byte limit')
                    with temp_target.open('ab') as handle:
                        handle.write(chunk)
                if file_size == 0:
                    validation_errors.append(f'{kind} - {name}: empty file')
                    continue
                original_max_pixels = Image.MAX_IMAGE_PIXELS
                try:
                    Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS
                    with warnings.catch_warnings():
                        warnings.simplefilter('error', Image.DecompressionBombWarning)
                        with Image.open(temp_target) as image:
                            image.verify()
                finally:
                    Image.MAX_IMAGE_PIXELS = original_max_pixels
                temp_target.replace(target)
            except ValueError as exc:
                temp_target.unlink(missing_ok=True)
                validation_errors.append(f'{kind} - {name}: {exc}')
                break
            except (UnidentifiedImageError, OSError, Image.DecompressionBombWarning):
                temp_target.unlink(missing_ok=True)
                validation_errors.append(f'{kind} - {name}: unreadable, corrupt, or unsafe image')
                continue
            finally:
                await upload.close()
            stored_files.append(name)
        return stored_files, validation_errors

    try:
        mapir_stored_files, mapir_errors = await _store_images('MAPIR', mapir_files, mapir_dir)
        rgb_stored_files, rgb_errors = await _store_images('RGB', rgb_files, rgb_dir)
        errors = [*mapir_errors, *rgb_errors]

        if len(mapir_stored_files) < deps.MINIMUM_DATASET_IMAGES:
            errors.append(f'MAPIR: at least {deps.MINIMUM_DATASET_IMAGES} valid images are required.')
        if len(rgb_stored_files) < deps.MINIMUM_DATASET_IMAGES:
            errors.append(f'RGB: at least {deps.MINIMUM_DATASET_IMAGES} valid images are required.')
        if errors:
            raise HTTPException(status_code=400, detail=errors)

        manifest = UploadManifest(
            run_id=upload_run_id,
            dataset_name=dataset_name,
            upload_dir=str(upload_dir),
            files=sorted([f'mapir/{name}' for name in mapir_stored_files] + [f'rgb/{name}' for name in rgb_stored_files]),
            mapir_files=sorted(mapir_stored_files),
            rgb_files=sorted(rgb_stored_files),
            created_at=datetime.now(timezone.utc),
        )
        deps.storage_service.write_json(upload_dir / 'manifest.json', manifest.model_dump(mode='json'))
        return manifest.model_dump(mode='json')
    except Exception:
        shutil.rmtree(upload_dir, ignore_errors=True)
        raise


@router.post('/ui/uploads')
async def upload_images_ui(
    dataset_name: str = Form(...),
    mapir_files: list[UploadFile] = File(...),
    rgb_files: list[UploadFile] = File(...),
) -> RedirectResponse:
    manifest = await upload_images(dataset_name=dataset_name, mapir_files=mapir_files, rgb_files=rgb_files)
    return RedirectResponse(url=f"/runs/new?upload_run_id={manifest['run_id']}", status_code=303)


@router.post('/ui/orthophotos')
async def create_orthophotos_ui(
    dataset_name: str = Form(...),
    mapir_files: list[UploadFile] = File(...),
    rgb_files: list[UploadFile] = File(...),
    orthophoto_preset: str = Form('balanced'),
    reduce_images: bool | None = Form(None),
) -> RedirectResponse:
    preset = ORTHOPHOTO_PRESET_VALUES.get(orthophoto_preset, ORTHOPHOTO_PRESET_VALUES['balanced'])
    should_reduce_images = preset['reduce_images'] if reduce_images is None else reduce_images
    manifest = await upload_images(dataset_name=dataset_name, mapir_files=mapir_files, rgb_files=rgb_files)
    run_request = RunCreateRequest.model_validate(
        {
            'run_name': f"{manifest['dataset_name']} orthophotos",
            'dataset_name': manifest['dataset_name'],
            'upload_run_id': manifest['run_id'],
            'selected_steps': {
                'resize_images': should_reduce_images,
                'run_odm': True,
                'fetch_weather': False,
                'run_irrigation': False,
                'run_pdm': False,
                'generate_report': False,
            },
            'parameters': {
                'orthophoto_preset': orthophoto_preset,
                'orthophoto_resolution_cm': preset['resolution_cm'],
            },
        }
    )
    record = deps.run_service.create_run_record(run_request)
    try:
        result = deps.run_service.start_run(record.run_id)
    except RunStartBlocked as exc:
        result = deps.run_service.mark_start_blocked(record.run_id, str(exc))
    return RedirectResponse(url=f'/runs/{result.run_id}', status_code=303)
