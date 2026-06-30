from __future__ import annotations

import shutil
import time
import warnings
import threading
from datetime import datetime, timezone
from pathlib import Path

import rasterio
from fastapi import APIRouter, Body, File, Form, HTTPException, UploadFile
from fastapi.responses import RedirectResponse
from PIL import Image, UnidentifiedImageError
from rasterio.errors import RasterioIOError

from agrivision.app import dependencies as deps
from agrivision.app.schemas.runs import RunCreateRequest, StageStatus, UploadManifest
from agrivision.config import load_config
from agrivision.services.run_service import RunStartBlocked

router = APIRouter()

UPLOAD_STREAM_CHUNK_SIZE = 1024 * 1024
MAX_FILES_PER_GROUP = 1000
MAX_DATASET_BYTES = 2 * 1024 * 1024 * 1024
MAX_IMAGE_PIXELS = 100_000_000

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
UPLOAD_VALIDATE_STAGE = 'upload_validate'
PENDING_UPLOAD_TIMEOUT_SECONDS = 300


def _selected_uploads(uploads: list[UploadFile]) -> list[UploadFile]:
    return [upload for upload in uploads if Path(upload.filename or '').name]


def _has_upload(upload: UploadFile | None) -> bool:
    return upload is not None and bool(Path(upload.filename or '').name)


def _log_run_event(run_id: str, message: str) -> None:
    try:
        record = deps.run_service.load_run(run_id)
        timestamp = datetime.now(timezone.utc).isoformat()
        with Path(record.logs_path).open('a', encoding='utf-8') as handle:
            handle.write(f'[{timestamp}] {message}\n')
    except Exception:
        pass


def _with_upload_validation_stage(record) -> list[StageStatus]:
    return [
        StageStatus(
            key=UPLOAD_VALIDATE_STAGE,
            label='Upload / validate',
            state='running',
            message='Uploading / validating images',
        ),
        *[StageStatus.model_validate(stage.model_dump()) for stage in record.stages],
    ]


def _camera_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item) in CAMERA_KINDS]


def _create_pending_orthophoto_record(
    *,
    dataset_name: str,
    upload_run_id: str,
    orthophoto_preset: str,
    raw_camera_targets: list[str],
    import_camera_targets: list[str],
    source_orthophoto_run_id: str | None = None,
    notes: str | None = None,
):
    preset = ORTHOPHOTO_PRESET_VALUES.get(orthophoto_preset, ORTHOPHOTO_PRESET_VALUES['balanced'])
    has_raw = bool(raw_camera_targets)
    run_request = RunCreateRequest.model_validate(
        {
            'run_name': f'{dataset_name} completed orthophotos' if source_orthophoto_run_id else f'{dataset_name} orthophotos',
            'dataset_name': dataset_name,
            'upload_run_id': upload_run_id,
            'selected_steps': {
                'resize_images': False,
                'run_odm': has_raw,
                'fetch_weather': False,
                'run_irrigation': False,
                'run_pdm': False,
                'generate_report': False,
            },
            'parameters': {
                'orthophoto_preset': orthophoto_preset if has_raw else 'imported',
                'orthophoto_resolution_cm': preset['resolution_cm'] if has_raw else None,
                'source_orthophoto_run_id': source_orthophoto_run_id,
                'camera_targets': raw_camera_targets if has_raw else import_camera_targets,
                'import_camera_targets': import_camera_targets,
                'notes': notes,
            },
        }
    )
    record = deps.run_service.create_run_record(run_request)
    return deps.run_service.update_status(
        record.run_id,
        status='running',
        current_stage=UPLOAD_VALIDATE_STAGE,
        stage_message='Waiting for upload',
        progress_percent=1,
        started_at=record.created_at,
        stages=_with_upload_validation_stage(record),
    )


def _pending_upload_response(record) -> dict[str, str]:
    return {
        'run_id': record.run_id,
        'redirect': f'/runs/{record.run_id}',
        'upload_url': f'/ui/orthophotos/{record.run_id}/files',
    }


def _has_pending_upload_content(upload_dir: Path, run_id: str) -> bool:
    pending_root = upload_dir / '.pending' / 'orthophotos' / run_id
    if pending_root.exists():
        return any(path.is_file() for path in pending_root.rglob('*'))
    return any(path.is_file() for path in upload_dir.rglob('*') if path.name != 'manifest.json')


def _expire_pending_upload_if_idle(run_id: str, *, timeout_seconds: int = PENDING_UPLOAD_TIMEOUT_SECONDS) -> None:
    time.sleep(max(timeout_seconds, 1))
    try:
        record = deps.run_service.load_run(run_id)
    except FileNotFoundError:
        return
    if record.status != 'running':
        return
    if record.current_stage != UPLOAD_VALIDATE_STAGE or record.stage_message != 'Waiting for upload':
        return
    upload_dir = Path(record.input_path)
    if _has_pending_upload_content(upload_dir, run_id):
        return
    message = f'Upload did not start within {timeout_seconds} seconds.'
    _log_run_event(run_id, message)
    _fail_pending_orthophoto_run(run_id, [message], 'Upload timed out before files reached the dashboard.')


def _schedule_pending_upload_timeout(run_id: str, *, timeout_seconds: int = PENDING_UPLOAD_TIMEOUT_SECONDS) -> None:
    thread = threading.Thread(
        target=_expire_pending_upload_if_idle,
        kwargs={'run_id': run_id, 'timeout_seconds': timeout_seconds},
        daemon=True,
        name=f'agrivision-upload-timeout-{run_id}',
    )
    thread.start()


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


async def _spool_uploads(uploads: list[UploadFile], target_dir: Path) -> list[str]:
    stored_files: list[str] = []
    target_dir.mkdir(parents=True, exist_ok=True)
    for upload in uploads:
        name = Path(upload.filename or '').name
        if not name:
            continue
        data = await upload.read()
        target = target_dir / name
        target.write_bytes(data)
        stored_files.append(name)
    return stored_files


async def _spool_imported_orthophoto(upload: UploadFile | None, target: Path) -> bool:
    if not _has_upload(upload):
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    data = await upload.read()  # type: ignore[union-attr]
    target.write_bytes(data)
    return True


def _validate_spooled_images(kind: str, pending_dir: Path, target_dir: Path) -> tuple[list[str], list[str]]:
    seen_names: set[str] = set()
    stored_files: list[str] = []
    validation_errors: list[str] = []
    target_dir.mkdir(parents=True, exist_ok=True)
    if not pending_dir.exists():
        return stored_files, validation_errors
    for pending_file in sorted(pending_dir.iterdir()):
        if not pending_file.is_file():
            continue
        name = pending_file.name
        suffix = pending_file.suffix.lower()
        if suffix not in deps.ALLOWED_EXTENSIONS:
            validation_errors.append(f'{kind} - {name}: unsupported file type')
            continue
        if name in seen_names:
            validation_errors.append(f'{kind} - {name}: duplicate or invalid name')
            continue
        seen_names.add(name)
        if pending_file.stat().st_size <= 0:
            validation_errors.append(f'{kind} - {name}: empty file')
            continue
        target = target_dir / name
        shutil.copy2(pending_file, target)
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
    mapir_dir = upload_dir / 'mapir'
    rgb_dir = upload_dir / 'rgb'
    thermal_dir = upload_dir / 'thermal'
    mapir_dir.mkdir(parents=True, exist_ok=True)
    rgb_dir.mkdir(parents=True, exist_ok=True)
    thermal_dir.mkdir(parents=True, exist_ok=True)
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
        thermal_stored_files, thermal_errors = await _store_images('THERMAL', thermal_files, thermal_dir)
        stored = {
            'rgb': rgb_stored_files,
            'mapir': mapir_stored_files,
            'thermal': thermal_stored_files,
        }
        errors = [*mapir_errors, *rgb_errors, *thermal_errors, *_validate_uploaded_categories(stored)]
        if errors:
            raise HTTPException(status_code=400, detail=errors)

        manifest = _manifest_payload(upload_run_id, dataset_name, upload_dir, stored)
        deps.storage_service.write_json(upload_dir / 'manifest.json', manifest.model_dump(mode='json'))
        return manifest.model_dump(mode='json')
    except Exception:
        shutil.rmtree(upload_dir, ignore_errors=True)
        raise


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


@router.post('/ui/orthophotos/init')
async def init_orthophotos_ui(payload: dict = Body(...)) -> dict[str, str]:
    dataset_name = str(payload.get('dataset_name') or '').strip()
    if not dataset_name:
        raise HTTPException(status_code=400, detail='Dataset name is required.')
    raw_camera_targets = _camera_list(payload.get('raw_camera_targets'))
    import_camera_targets = _camera_list(payload.get('import_camera_targets'))
    if not raw_camera_targets and not import_camera_targets:
        raise HTTPException(status_code=400, detail='Choose raw images or a ready orthophoto for at least one camera.')
    upload_run_id = deps.storage_service.new_run_id()
    deps.storage_service.upload_dir(upload_run_id)
    record = _create_pending_orthophoto_record(
        dataset_name=dataset_name,
        upload_run_id=upload_run_id,
        orthophoto_preset=str(payload.get('orthophoto_preset') or 'balanced'),
        raw_camera_targets=raw_camera_targets,
        import_camera_targets=import_camera_targets,
        notes='Mixed ODM/import orthophoto intake' if raw_camera_targets and import_camera_targets else None,
    )
    _schedule_pending_upload_timeout(record.run_id)
    return _pending_upload_response(record)


@router.post('/ui/orthophotos/{run_id}/complete/init')
async def init_complete_orthophoto_dataset_ui(run_id: str, payload: dict = Body(...)) -> dict[str, str]:
    source_run = deps.run_service.load_run(run_id)
    upload_run_id = Path(source_run.input_path).name
    manifest = deps.storage_service.read_json(deps.storage_service.upload_dir(upload_run_id) / 'manifest.json', default={})
    dataset_name = str(manifest.get('dataset_name') or source_run.dataset_name)
    raw_camera_targets = _camera_list(payload.get('raw_camera_targets'))
    import_camera_targets = _camera_list(payload.get('import_camera_targets'))
    if not raw_camera_targets and not import_camera_targets:
        raise HTTPException(status_code=400, detail='Choose images or a ready orthophoto for at least one missing camera.')
    record = _create_pending_orthophoto_record(
        dataset_name=dataset_name,
        upload_run_id=upload_run_id,
        orthophoto_preset=str(payload.get('orthophoto_preset') or 'balanced'),
        raw_camera_targets=raw_camera_targets,
        import_camera_targets=import_camera_targets,
        source_orthophoto_run_id=run_id,
        notes='Completed missing orthophotos',
    )
    _schedule_pending_upload_timeout(record.run_id)
    return _pending_upload_response(record)


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
        'rgb': _selected_uploads(rgb_files) if source_modes['rgb'] == 'raw' else [],
        'mapir': _selected_uploads(mapir_files) if source_modes['mapir'] == 'raw' else [],
        'thermal': _selected_uploads(thermal_files) if source_modes['thermal'] == 'raw' else [],
    }
    ortho_uploads = {
        'rgb': rgb_orthophoto if source_modes['rgb'] == 'ortho' else None,
        'mapir': mapir_orthophoto if source_modes['mapir'] == 'ortho' else None,
        'thermal': thermal_orthophoto if source_modes['thermal'] == 'ortho' else None,
    }

    raw_camera_targets = [kind for kind in CAMERA_KINDS if raw_uploads[kind]]
    import_camera_targets = [kind for kind in CAMERA_KINDS if _has_upload(ortho_uploads[kind])]
    has_raw = bool(raw_camera_targets)
    has_import = bool(import_camera_targets)
    if not has_raw and not has_import:
        raise HTTPException(status_code=400, detail='Choose raw images or a ready orthophoto for at least one camera.')

    upload_run_id = deps.storage_service.new_run_id()
    upload_dir = deps.storage_service.upload_dir(upload_run_id)
    pending_root = upload_dir / '.pending' / 'orthophotos'
    run_camera_targets = raw_camera_targets if raw_camera_targets else import_camera_targets
    run_request = RunCreateRequest.model_validate(
        {
            'run_name': f'{dataset_name} orthophotos',
            'dataset_name': dataset_name,
            'upload_run_id': upload_run_id,
            'selected_steps': {
                'resize_images': False,
                'run_odm': has_raw,
                'fetch_weather': False,
                'run_irrigation': False,
                'run_pdm': False,
                'generate_report': False,
            },
            'parameters': {
                'orthophoto_preset': orthophoto_preset if has_raw else 'imported',
                'orthophoto_resolution_cm': preset['resolution_cm'] if has_raw else None,
                'camera_targets': run_camera_targets,
                'import_camera_targets': import_camera_targets,
                'notes': 'Mixed ODM/import orthophoto intake' if has_import and has_raw else None,
            },
        }
    )
    record = deps.run_service.create_run_record(run_request)
    deps.run_service.update_status(
        record.run_id,
        status='running',
        current_stage=UPLOAD_VALIDATE_STAGE,
        stage_message='Uploading / validating images',
        progress_percent=1,
        started_at=record.created_at,
        stages=_with_upload_validation_stage(record),
    )
    for camera_kind in raw_camera_targets:
        await _spool_uploads(raw_uploads[camera_kind], pending_root / 'raw' / camera_kind)
    for camera_kind in import_camera_targets:
        upload = ortho_uploads[camera_kind]
        suffix = Path(upload.filename).suffix.lower() if upload and upload.filename else '.tif'
        await _spool_imported_orthophoto(upload, pending_root / 'orthos' / f'orthophoto_{camera_kind}{suffix}')
    _start_pending_orthophoto_processing(
        run_id=record.run_id,
        upload_run_id=upload_run_id,
        dataset_name=dataset_name,
        pending_root=pending_root,
        raw_camera_targets=raw_camera_targets,
        import_camera_targets=import_camera_targets,
        existing_files={'rgb': [], 'mapir': [], 'thermal': []},
    )
    return RedirectResponse(url=f'/runs/{record.run_id}', status_code=303)


@router.post('/ui/orthophotos/{run_id}/upload/{camera_kind}')
async def upload_missing_orthophoto_camera_ui(
    run_id: str,
    camera_kind: str,
    files: list[UploadFile] = File(default=[]),
    orthophoto_file: UploadFile | None = File(default=None),
    source_mode: str = Form('raw'),
    orthophoto_preset: str = Form('balanced'),
) -> RedirectResponse:
    if camera_kind not in {'rgb', 'mapir', 'thermal'}:
        raise HTTPException(status_code=404, detail='Camera category not found.')
    source_run = deps.run_service.load_run(run_id)
    upload_run_id = Path(source_run.input_path).name
    upload_dir = deps.storage_service.upload_dir(upload_run_id)
    manifest = deps.storage_service.read_json(upload_dir / 'manifest.json', default={})
    dataset_name = str(manifest.get('dataset_name') or source_run.dataset_name)
    if source_mode == 'ortho':
        run_request = RunCreateRequest.model_validate(
            {
                'run_name': f'{dataset_name} {camera_kind.upper()} imported orthophoto',
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
                    'source_orthophoto_run_id': run_id,
                    'camera_targets': [camera_kind],
                    'notes': f'Imported ready {camera_kind.upper()} orthophoto',
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
        path, errors = await _store_imported_orthophoto(camera_kind, orthophoto_file, output_dir)
        if errors or not path:
            deps.run_service.update_status(
                record.run_id,
                status='failed',
                errors=errors or [f'{camera_kind.upper()}: choose a ready orthophoto.'],
                current_stage='import_orthophotos',
                stage_message='Imported orthophoto validation failed.',
            )
            raise HTTPException(status_code=400, detail=errors or [f'{camera_kind.upper()}: choose a ready orthophoto.'])
        completed = deps.run_service.update_status(
            record.run_id,
            status='completed',
            outputs={ORTHOPHOTO_OUTPUT_KEYS[camera_kind]: path},
            progress_percent=100,
            current_stage='completed',
            stage_message='Premade orthophoto imported.',
            started_at=record.created_at,
            finished_at=record.created_at,
        )
        return RedirectResponse(url=f'/runs/{completed.run_id}', status_code=303)

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


@router.post('/ui/orthophotos/{run_id}/complete')
async def complete_orthophoto_dataset_ui(
    run_id: str,
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
) -> RedirectResponse:
    source_run = deps.run_service.load_run(run_id)
    upload_run_id = Path(source_run.input_path).name
    upload_dir = deps.storage_service.upload_dir(upload_run_id)
    manifest = deps.storage_service.read_json(upload_dir / 'manifest.json', default={})
    dataset_name = str(manifest.get('dataset_name') or source_run.dataset_name)
    source_modes = {
        'rgb': rgb_source if rgb_source in {'raw', 'ortho'} else 'raw',
        'mapir': mapir_source if mapir_source in {'raw', 'ortho'} else 'raw',
        'thermal': thermal_source if thermal_source in {'raw', 'ortho'} else 'raw',
    }
    raw_uploads = {
        'rgb': _selected_uploads(rgb_files) if source_modes['rgb'] == 'raw' else [],
        'mapir': _selected_uploads(mapir_files) if source_modes['mapir'] == 'raw' else [],
        'thermal': _selected_uploads(thermal_files) if source_modes['thermal'] == 'raw' else [],
    }
    ortho_uploads = {
        'rgb': rgb_orthophoto if source_modes['rgb'] == 'ortho' else None,
        'mapir': mapir_orthophoto if source_modes['mapir'] == 'ortho' else None,
        'thermal': thermal_orthophoto if source_modes['thermal'] == 'ortho' else None,
    }

    existing = {
        'rgb': list(manifest.get('rgb_files', [])),
        'mapir': list(manifest.get('mapir_files', [])),
        'thermal': list(manifest.get('thermal_files', [])),
    }
    raw_camera_targets = [kind for kind in CAMERA_KINDS if raw_uploads[kind]]
    import_camera_targets = [kind for kind in CAMERA_KINDS if _has_upload(ortho_uploads[kind])]
    if not raw_camera_targets and not import_camera_targets:
        raise HTTPException(status_code=400, detail='Choose images or a ready orthophoto for at least one missing camera.')

    preset = ORTHOPHOTO_PRESET_VALUES.get(orthophoto_preset, ORTHOPHOTO_PRESET_VALUES['balanced'])
    pending_root = upload_dir / '.pending' / 'orthophotos' / deps.storage_service.new_run_id()
    run_request = RunCreateRequest.model_validate(
        {
            'run_name': f'{dataset_name} completed orthophotos',
            'dataset_name': dataset_name,
            'upload_run_id': upload_run_id,
            'selected_steps': {
                'resize_images': False,
                'run_odm': bool(raw_camera_targets),
                'fetch_weather': False,
                'run_irrigation': False,
                'run_pdm': False,
                'generate_report': False,
            },
            'parameters': {
                'orthophoto_preset': orthophoto_preset if raw_camera_targets else 'imported',
                'orthophoto_resolution_cm': preset['resolution_cm'] if raw_camera_targets else None,
                'source_orthophoto_run_id': run_id,
                'camera_targets': raw_camera_targets if raw_camera_targets else import_camera_targets,
                'import_camera_targets': import_camera_targets,
                'notes': 'Completed missing orthophotos',
            },
        }
    )
    record = deps.run_service.create_run_record(run_request)
    deps.run_service.update_status(
        record.run_id,
        status='running',
        current_stage=UPLOAD_VALIDATE_STAGE,
        stage_message='Uploading / validating images',
        progress_percent=1,
        started_at=record.created_at,
        stages=_with_upload_validation_stage(record),
    )
    for camera_kind in raw_camera_targets:
        await _spool_uploads(raw_uploads[camera_kind], pending_root / 'raw' / camera_kind)
    for camera_kind in import_camera_targets:
        upload = ortho_uploads[camera_kind]
        suffix = Path(upload.filename).suffix.lower() if upload and upload.filename else '.tif'
        await _spool_imported_orthophoto(upload, pending_root / 'orthos' / f'orthophoto_{camera_kind}{suffix}')
    _start_pending_orthophoto_processing(
        run_id=record.run_id,
        upload_run_id=upload_run_id,
        dataset_name=dataset_name,
        pending_root=pending_root,
        raw_camera_targets=raw_camera_targets,
        import_camera_targets=import_camera_targets,
        existing_files=existing,
    )
    return RedirectResponse(url=f'/runs/{record.run_id}', status_code=303)


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
    return _validate_imported_orthophoto_path(camera_kind, target)


def _store_pending_imported_orthophoto(camera_kind: str, source: Path, target_dir: Path) -> tuple[str | None, list[str]]:
    if not source.exists():
        return None, [f'{camera_kind.upper()} orthophoto file is missing.']
    suffix = source.suffix.lower()
    if suffix not in {'.tif', '.tiff'}:
        return None, [f'{camera_kind.upper()} orthophoto must be a GeoTIFF (.tif or .tiff).']
    if source.stat().st_size <= 0:
        return None, [f'{camera_kind.upper()} orthophoto file is empty.']
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f'orthophoto_{camera_kind}.tif'
    shutil.copy2(source, target)
    return _validate_imported_orthophoto_path(camera_kind, target)


def _validate_imported_orthophoto_path(camera_kind: str, target: Path) -> tuple[str | None, list[str]]:
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


def _fail_pending_orthophoto_run(run_id: str, errors: list[str], message: str) -> None:
    _log_run_event(run_id, message)
    for error in errors:
        _log_run_event(run_id, error)
    deps.run_service.update_stage(run_id, UPLOAD_VALIDATE_STAGE, 'failed', message)
    deps.run_service.update_status(
        run_id,
        status='failed',
        errors=errors,
        current_stage=UPLOAD_VALIDATE_STAGE,
        stage_message=message,
        finished_at=datetime.now(timezone.utc),
    )


def _process_pending_orthophoto_run(
    *,
    run_id: str,
    upload_run_id: str,
    dataset_name: str,
    pending_root: Path,
    raw_camera_targets: list[str],
    import_camera_targets: list[str],
    existing_files: dict[str, list[str]] | None = None,
) -> None:
    upload_dir = deps.storage_service.upload_dir(upload_run_id)
    stored = {
        'rgb': list((existing_files or {}).get('rgb', [])),
        'mapir': list((existing_files or {}).get('mapir', [])),
        'thermal': list((existing_files or {}).get('thermal', [])),
    }
    validation_errors: list[str] = []
    imported_outputs: dict[str, str] = {}
    try:
        _log_run_event(run_id, 'Uploading / validating images')
        for camera_kind in raw_camera_targets:
            files, errors = _validate_spooled_images(
                camera_kind.upper(),
                pending_root / 'raw' / camera_kind,
                upload_dir / camera_kind,
            )
            validation_errors.extend(errors)
            if len(files) < deps.MINIMUM_DATASET_IMAGES:
                validation_errors.append(
                    f'{camera_kind.upper()}: at least {deps.MINIMUM_DATASET_IMAGES} valid images are required.'
                )
                continue
            stored[camera_kind] = sorted(set(stored.get(camera_kind, [])) | set(files))

        if validation_errors:
            _fail_pending_orthophoto_run(run_id, validation_errors, 'Image validation failed.')
            return

        manifest = _manifest_payload(upload_run_id, dataset_name, upload_dir, stored)
        deps.storage_service.write_json(upload_dir / 'manifest.json', manifest.model_dump(mode='json'))

        config = load_config()
        output_dir = (
            deps.storage_service.layout.project_root
            / config['paths'].get('runs_output', 'output/runs')
            / run_id
            / 'orthophotos'
        )
        import_errors: list[str] = []
        for camera_kind in import_camera_targets:
            source_candidates = list((pending_root / 'orthos').glob(f'orthophoto_{camera_kind}.*'))
            source = source_candidates[0] if source_candidates else pending_root / 'orthos' / f'orthophoto_{camera_kind}.tif'
            path, errors = _store_pending_imported_orthophoto(camera_kind, source, output_dir)
            import_errors.extend(errors)
            if path:
                imported_outputs[ORTHOPHOTO_OUTPUT_KEYS[camera_kind]] = path

        if import_errors:
            _fail_pending_orthophoto_run(run_id, import_errors, 'Imported orthophoto validation failed.')
            return

        if imported_outputs:
            deps.run_service.update_status(run_id, outputs=imported_outputs)
        deps.run_service.update_stage(run_id, UPLOAD_VALIDATE_STAGE, 'completed', 'Uploads validated')

        if not raw_camera_targets:
            deps.run_service.update_status(
                run_id,
                status='completed',
                outputs=imported_outputs,
                progress_percent=100,
                current_stage='completed',
                stage_message='Premade orthophotos imported.',
                started_at=datetime.now(timezone.utc),
                finished_at=datetime.now(timezone.utc),
            )
            _log_run_event(run_id, 'Premade orthophotos imported.')
            return

        try:
            deps.run_service.start_run(run_id)
        except RunStartBlocked as exc:
            deps.run_service.mark_start_blocked(run_id, str(exc))
    except Exception as exc:
        _fail_pending_orthophoto_run(run_id, [str(exc)], 'Upload processing failed.')


def _start_pending_orthophoto_processing(**kwargs) -> None:
    thread = threading.Thread(
        target=_process_pending_orthophoto_run,
        kwargs=kwargs,
        daemon=True,
        name=f'agrivision-upload-{kwargs["run_id"]}',
    )
    thread.start()


@router.post('/ui/orthophotos/{run_id}/files')
async def upload_pending_orthophoto_files_ui(
    run_id: str,
    mapir_files: list[UploadFile] = File(default=[]),
    rgb_files: list[UploadFile] = File(default=[]),
    thermal_files: list[UploadFile] = File(default=[]),
    rgb_orthophoto: UploadFile | None = File(default=None),
    mapir_orthophoto: UploadFile | None = File(default=None),
    thermal_orthophoto: UploadFile | None = File(default=None),
    rgb_source: str = Form('raw'),
    mapir_source: str = Form('raw'),
    thermal_source: str = Form('raw'),
) -> dict[str, str]:
    record = deps.run_service.load_run(run_id)
    upload_run_id = Path(record.input_path).name
    upload_dir = deps.storage_service.upload_dir(upload_run_id)
    source_run_id = record.parameters.get('source_orthophoto_run_id')
    source_modes = {
        'rgb': rgb_source if rgb_source in {'raw', 'ortho'} else 'raw',
        'mapir': mapir_source if mapir_source in {'raw', 'ortho'} else 'raw',
        'thermal': thermal_source if thermal_source in {'raw', 'ortho'} else 'raw',
    }
    raw_uploads = {
        'rgb': _selected_uploads(rgb_files) if source_modes['rgb'] == 'raw' else [],
        'mapir': _selected_uploads(mapir_files) if source_modes['mapir'] == 'raw' else [],
        'thermal': _selected_uploads(thermal_files) if source_modes['thermal'] == 'raw' else [],
    }
    ortho_uploads = {
        'rgb': rgb_orthophoto if source_modes['rgb'] == 'ortho' else None,
        'mapir': mapir_orthophoto if source_modes['mapir'] == 'ortho' else None,
        'thermal': thermal_orthophoto if source_modes['thermal'] == 'ortho' else None,
    }
    raw_camera_targets = [kind for kind in CAMERA_KINDS if raw_uploads[kind]]
    import_camera_targets = [kind for kind in CAMERA_KINDS if _has_upload(ortho_uploads[kind])]
    if not raw_camera_targets and not import_camera_targets:
        _fail_pending_orthophoto_run(run_id, ['No files were uploaded.'], 'Upload failed.')
        raise HTTPException(status_code=400, detail='No files were uploaded.')

    existing = {'rgb': [], 'mapir': [], 'thermal': []}
    if source_run_id:
        manifest = deps.storage_service.read_json(upload_dir / 'manifest.json', default={})
        existing = {
            'rgb': list(manifest.get('rgb_files', [])),
            'mapir': list(manifest.get('mapir_files', [])),
            'thermal': list(manifest.get('thermal_files', [])),
        }

    deps.run_service.update_status(
        run_id,
        status='running',
        current_stage=UPLOAD_VALIDATE_STAGE,
        stage_message='Upload received; validating images',
        progress_percent=max(record.progress_percent, 2),
    )
    _log_run_event(run_id, 'Upload received; validating images')
    pending_root = upload_dir / '.pending' / 'orthophotos' / run_id
    for camera_kind in raw_camera_targets:
        await _spool_uploads(raw_uploads[camera_kind], pending_root / 'raw' / camera_kind)
    for camera_kind in import_camera_targets:
        upload = ortho_uploads[camera_kind]
        suffix = Path(upload.filename).suffix.lower() if upload and upload.filename else '.tif'
        await _spool_imported_orthophoto(upload, pending_root / 'orthos' / f'orthophoto_{camera_kind}{suffix}')
    _start_pending_orthophoto_processing(
        run_id=record.run_id,
        upload_run_id=upload_run_id,
        dataset_name=record.dataset_name,
        pending_root=pending_root,
        raw_camera_targets=raw_camera_targets,
        import_camera_targets=import_camera_targets,
        existing_files=existing,
    )
    return {'run_id': record.run_id, 'redirect': f'/runs/{record.run_id}'}


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
