from __future__ import annotations

import contextlib
import json
import re
import shutil
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path

from agrivision.app.schemas.runs import (
    ArtifactRecord,
    RunCreateRequest,
    RunRecord,
    StageStatus,
    StepSelection,
)
from agrivision.config import load_config
from agrivision.pipeline.orchestrator import run_full_pipeline
from agrivision.services.failure_diagnostics import summarize_failure
from agrivision.services.run_workspace import RunWorkspace
from agrivision.services.storage_service import StorageService


def _slugify_report_name(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", value.strip()).strip("-").lower()
    return slug or "report"


def _timestamp_report_name() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


class RunCancelled(RuntimeError):
    pass


class RunStartBlocked(RuntimeError):
    pass


class RunService:
    RESTART_RECONCILIATION_MESSAGE = 'Interrupted because the dashboard process restarted before the run completed.'
    CORRUPTED_RUN_MESSAGE = 'Run record is corrupted and requires manual cleanup.'

    def __init__(self, storage: StorageService | None = None) -> None:
        self.storage = storage or StorageService()
        self._lock = threading.Lock()
        self._threads: dict[str, threading.Thread] = {}
        self._cancel_events: dict[str, threading.Event] = {}

    def create_run_record(self, request: RunCreateRequest) -> RunRecord:
        run_id = self.storage.new_run_id()
        run_dir = self.storage.run_dir(run_id)
        upload_dir = self.storage.upload_dir(request.upload_run_id)
        created_at = datetime.now(timezone.utc)
        record = RunRecord(
            run_id=run_id,
            created_at=created_at,
            updated_at=created_at,
            started_at=None,
            finished_at=None,
            dataset_name=request.dataset_name,
            input_path=str(upload_dir),
            status='queued',
            progress_percent=0,
            current_stage='queued',
            stage_message='Queued',
            selected_steps=request.selected_steps,
            parameters={
                'preset': request.parameters.preset,
                'notes': request.parameters.notes,
                'flight_date': request.parameters.flight_date.isoformat() if request.parameters.flight_date else None,
                'orthophoto_preset': request.parameters.orthophoto_preset,
                'orthophoto_resolution_cm': request.parameters.orthophoto_resolution_cm,
                'source_orthophoto_run_id': request.parameters.source_orthophoto_run_id,
                'camera_targets': request.parameters.camera_targets,
                'import_camera_targets': request.parameters.import_camera_targets,
                'pdm_crop': request.parameters.pdm_crop,
                'pdm_model_key': request.parameters.pdm_model_key,
            },
            outputs={},
            errors=[],
            stages=self._build_stages(request.selected_steps),
            logs_path=str(run_dir / 'run.log'),
            run_name=request.run_name,
            field_name=request.field_name,
            run_dir=str(run_dir),
        )
        self._write_record_files(record)
        return record

    @staticmethod
    def _is_orthophoto_creation_run(record_or_steps) -> bool:
        selected = getattr(record_or_steps, 'selected_steps', record_or_steps)
        return (
            selected.run_odm
            and not selected.fetch_weather
            and not selected.run_irrigation
            and not selected.run_pdm
            and not selected.generate_report
        )

    def _build_stages(self, selected_steps) -> list[StageStatus]:
        stages = [StageStatus(key='stage_inputs', label='Stage inputs')]
        if selected_steps.run_odm:
            stages.extend([
                StageStatus(key='run_odm_rgb', label='Run ODM RGB'),
                StageStatus(key='run_odm_mapir', label='Run ODM MAPIR'),
                StageStatus(key='run_odm_thermal', label='Run ODM thermal'),
            ])
        if self._is_orthophoto_creation_run(selected_steps):
            return stages
        stages.extend([
            StageStatus(key='compute_vegetation_index', label='Compute Vegetation Index'),
            StageStatus(key='generate_grid', label='Generate grid'),
        ])
        if selected_steps.fetch_weather:
            stages.append(StageStatus(key='fetch_weather', label='Fetch weather'))
        if selected_steps.run_irrigation:
            stages.append(StageStatus(key='irrigation_enrichment', label='Irrigation enrichment'))
        if selected_steps.run_pdm:
            stages.append(StageStatus(key='pdm_enrichment', label='Pest & disease enrichment'))
        stages.append(StageStatus(key='disease_risk', label='Score disease risk'))
        if selected_steps.generate_report:
            stages.append(StageStatus(key='generate_report', label='Generate report'))
        return stages

    def _write_record_files(self, record: RunRecord) -> None:
        run_dir = Path(record.run_dir)
        self.storage.write_json(run_dir / 'params.json', {
            'run_name': record.run_name,
            'dataset_name': record.dataset_name,
            'field_name': record.field_name,
            'selected_steps': record.selected_steps.model_dump(),
            'parameters': record.parameters,
            'input_path': record.input_path,
        })
        self.storage.write_json(run_dir / 'status.json', record.model_dump(mode='json'))
        self.storage.write_json(run_dir / 'outputs.json', record.outputs)
        self.storage.write_json(run_dir / 'artifacts.json', record.artifacts)
        Path(record.logs_path).touch(exist_ok=True)

    def workspace_for_run(self, run_id: str) -> RunWorkspace:
        return self.workspace_for_record(self.load_run(run_id))

    def workspace_for_record(self, record: RunRecord) -> RunWorkspace:
        return RunWorkspace.from_run_record(record, self.storage)

    def load_run(self, run_id: str) -> RunRecord:
        path = self.storage.layout.runs_root / run_id / 'status.json'
        if not path.exists():
            raise FileNotFoundError(f'Run not found: {run_id}')
        return self._load_run_record(path)

    def list_runs(self) -> list[RunRecord]:
        runs: list[RunRecord] = []
        for status_path in sorted(self.storage.layout.runs_root.glob('*/status.json'), reverse=True):
            runs.append(self._load_run_record(status_path))
        runs.sort(key=lambda item: item.created_at, reverse=True)
        return runs

    def _load_run_record(self, status_path: Path) -> RunRecord:
        try:
            return RunRecord.model_validate(self.storage.read_json(status_path))
        except Exception as exc:
            return self._corrupted_run_record(status_path, exc)

    def _corrupted_run_record(self, status_path: Path, exc: Exception) -> RunRecord:
        run_dir = status_path.parent
        payload: dict[str, object] = {}
        with contextlib.suppress(OSError, json.JSONDecodeError):
            loaded = json.loads(status_path.read_text(encoding='utf-8'))
            if isinstance(loaded, dict):
                payload = loaded
        now = datetime.now(timezone.utc)
        return RunRecord(
            run_id=str(payload.get('run_id') or run_dir.name),
            created_at=now,
            updated_at=now,
            started_at=None,
            finished_at=now,
            dataset_name=str(payload.get('dataset_name') or run_dir.name),
            input_path=str(payload.get('input_path') or ''),
            status='failed',
            progress_percent=0,
            current_stage='corrupted',
            stage_message=self.CORRUPTED_RUN_MESSAGE,
            selected_steps=StepSelection.model_validate(payload.get('selected_steps') or {}),
            parameters={},
            outputs={},
            errors=[f'{self.CORRUPTED_RUN_MESSAGE} ({exc})'],
            stages=[],
            logs_path=str(payload.get('logs_path') or (run_dir / 'run.log')),
            run_name=str(payload.get('run_name')) if payload.get('run_name') else None,
            field_name=str(payload.get('field_name')) if payload.get('field_name') else None,
            run_dir=str(payload.get('run_dir') or run_dir),
        )

    def _existing_run_dir(self, run_id: str) -> Path:
        candidate = (self.storage.layout.runs_root / run_id).resolve()
        runs_root = self.storage.layout.runs_root.resolve()
        if runs_root not in candidate.parents or not (candidate / 'status.json').exists():
            raise FileNotFoundError(f'Run not found: {run_id}')
        return candidate

    def _runs_output_root(self) -> Path:
        relative_root = load_config()['paths'].get('runs_output', 'output/runs')
        return self.storage.layout.project_root / relative_root

    def _run_output_dir(self, run_id: str) -> Path:
        return self._runs_output_root() / run_id

    def _run_orthophoto_output_dir(self, run_id: str) -> Path:
        return self._run_output_dir(run_id) / 'orthophotos'

    def delete_run(self, run_id: str) -> None:
        run_dir = self._existing_run_dir(run_id)
        record = RunRecord.model_validate(self.storage.read_json(run_dir / 'status.json'))
        if record.status in {'queued', 'running'}:
            raise ValueError('Active runs must be stopped before deletion.')
        shutil.rmtree(run_dir)
        run_output_dir = self._run_output_dir(run_id)
        if run_output_dir.exists():
            shutil.rmtree(run_output_dir)

    def archive_run(self, run_id: str) -> Path:
        run_dir = self._existing_run_dir(run_id)
        record = RunRecord.model_validate(self.storage.read_json(run_dir / 'status.json'))
        if record.status in {'queued', 'running'}:
            raise ValueError('Active runs must be stopped before archiving.')
        archive_root = self.storage.layout.runtime_root / 'archived_runs'
        archive_root.mkdir(parents=True, exist_ok=True)
        destination = archive_root / run_id
        if destination.exists():
            shutil.rmtree(destination)
        shutil.move(str(run_dir), str(destination))
        return destination

    def clear_stuck_active_runs(self) -> list[RunRecord]:
        cleared: list[RunRecord] = []
        for record in self.list_runs():
            if record.status not in {'queued', 'running'}:
                continue
            thread = self._threads.get(record.run_id)
            if thread is not None and thread.is_alive():
                continue
            cleared.append(
                self.finalize_run_status(
                    record.run_id,
                    status='cancelled',
                    current_stage='cancelled',
                    stage_message='Cleared stale active run.',
                    error_message='Cleared stale active run.',
                    running_stage_state='cancelled',
                    running_stage_message='Cleared stale active run.',
                )
            )
        return cleared

    def reconcile_orphaned_runs(self) -> list[RunRecord]:
        reconciled: list[RunRecord] = []
        for record in self.list_runs():
            if record.status not in {'queued', 'running'}:
                continue
            reconciled.append(
                self.finalize_run_status(
                    record.run_id,
                    status='cancelled',
                    current_stage='cancelled',
                    stage_message=self.RESTART_RECONCILIATION_MESSAGE,
                    error_message=self.RESTART_RECONCILIATION_MESSAGE,
                    running_stage_state='cancelled',
                    running_stage_message=self.RESTART_RECONCILIATION_MESSAGE,
                )
            )
        return reconciled

    def clear_incomplete_runs(self) -> int:
        cleared = 0
        for record in self.list_runs():
            if record.status in {'failed', 'cancelled'}:
                self.delete_run(record.run_id)
                cleared += 1
                continue
            if record.status not in {'queued', 'running'}:
                continue
            thread = self._threads.get(record.run_id)
            if thread is not None and thread.is_alive():
                continue
            self.finalize_run_status(
                record.run_id,
                status='cancelled',
                current_stage='cancelled',
                stage_message='Cleared incomplete run.',
                error_message='Cleared incomplete run.',
                running_stage_state='cancelled',
                running_stage_message='Cleared incomplete run.',
            )
            self.delete_run(record.run_id)
            cleared += 1
        return cleared

    def update_status(
        self,
        run_id: str,
        *,
        status: str | None = None,
        outputs: dict[str, str] | None = None,
        artifacts: dict[str, ArtifactRecord] | None = None,
        errors: list[str] | None = None,
        progress_percent: int | None = None,
        current_stage: str | None = None,
        stage_message: str | None = None,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
        stages: list[StageStatus] | None = None,
    ) -> RunRecord:
        with self._lock:
            record = self.load_run(run_id)
            run_dir = self.storage.run_dir(run_id)
            if status is not None:
                record.status = status  # type: ignore[misc]
            record.updated_at = datetime.now(timezone.utc)
            if outputs is not None:
                record.outputs = outputs
                self.storage.write_json(run_dir / 'outputs.json', outputs)
            if artifacts is not None:
                record.artifacts = artifacts
                self.storage.write_json(run_dir / 'artifacts.json', {key: value.model_dump(mode='json') for key, value in artifacts.items()})
            if errors is not None:
                record.errors = errors
            if progress_percent is not None:
                record.progress_percent = progress_percent
            if current_stage is not None:
                record.current_stage = current_stage
            if stage_message is not None:
                record.stage_message = stage_message
            if started_at is not None:
                record.started_at = started_at
            if finished_at is not None:
                record.finished_at = finished_at
            if stages is not None:
                record.stages = stages
            self.storage.write_json(run_dir / 'status.json', record.model_dump(mode='json'))
            return record

    def _progress_for_stages(self, stages: list[StageStatus]) -> int:
        if not stages:
            return 0
        score = 0.0
        for stage in stages:
            if stage.state in {'completed', 'skipped'}:
                score += 1.0
            elif stage.state == 'running':
                score += 0.5
        return int((score / len(stages)) * 100)

    def update_stage(self, run_id: str, stage_key: str, state: str, message: str | None = None) -> RunRecord:
        record = self.load_run(run_id)
        stages = [StageStatus.model_validate(stage.model_dump()) for stage in record.stages]
        label = stage_key.replace('_', ' ').title()
        matched = False
        for stage in stages:
            if stage.key == stage_key:
                stage.state = state  # type: ignore[misc]
                stage.message = message
                label = stage.label
                matched = True
            elif state == 'running' and stage.state == 'running':
                stage.state = 'completed'
        if not matched:
            stages.append(StageStatus(key=stage_key, label=label, state=state, message=message))
        progress_percent = self._progress_for_stages(stages)
        if state == 'completed' and progress_percent < 100:
            progress_percent = min(progress_percent, 99)
        return self.update_status(
            run_id,
            status='running' if state not in {'failed'} else 'failed',
            progress_percent=progress_percent,
            current_stage=stage_key,
            stage_message=message or label,
            stages=stages,
        )

    def _cancel_stages(self, stages: list[StageStatus]) -> list[StageStatus]:
        return self._finalize_stages(
            stages,
            running_state='cancelled',
            running_message='Stopped by operator.',
        )

    def _finalize_stages(
        self,
        stages: list[StageStatus],
        *,
        running_state: str,
        running_message: str | None,
        pending_state: str = 'skipped',
    ) -> list[StageStatus]:
        finalized_stages = [StageStatus.model_validate(stage.model_dump()) for stage in stages]
        for stage in finalized_stages:
            if stage.state == 'running':
                stage.state = running_state  # type: ignore[misc]
                stage.message = running_message
            elif stage.state == 'pending':
                stage.state = pending_state  # type: ignore[misc]
        return finalized_stages

    def _append_unique_error(self, errors: list[str], message: str) -> list[str]:
        return errors if message in errors else [*errors, message]

    def finalize_run_status(
        self,
        run_id: str,
        *,
        status: str,
        current_stage: str,
        stage_message: str,
        outputs: dict[str, str] | None = None,
        errors: list[str] | None = None,
        error_message: str | None = None,
        running_stage_state: str | None = None,
        running_stage_message: str | None = None,
        progress_percent: int | None = None,
    ) -> RunRecord:
        record = self.load_run(run_id)
        final_errors = errors
        if final_errors is None:
            final_errors = record.errors if error_message is None else self._append_unique_error(record.errors, error_message)
        stages = record.stages
        if running_stage_state is not None:
            stages = self._finalize_stages(
                record.stages,
                running_state=running_stage_state,
                running_message=running_stage_message,
            )
        return self.update_status(
            run_id,
            status=status,
            outputs=outputs,
            errors=final_errors,
            progress_percent=progress_percent,
            current_stage=current_stage,
            stage_message=stage_message,
            finished_at=record.finished_at or datetime.now(timezone.utc),
            stages=stages,
        )

    def _active_run_blocker(self, run_id: str) -> RunRecord | None:
        for candidate in self.list_runs():
            if candidate.run_id == run_id:
                continue
            if candidate.status in {'queued', 'running'}:
                return candidate
        return None

    def mark_start_blocked(self, run_id: str, message: str) -> RunRecord:
        return self.finalize_run_status(
            run_id,
            status='cancelled',
            current_stage='blocked',
            stage_message=message,
            error_message=message,
            running_stage_state='cancelled',
            running_stage_message=message,
        )

    def stage_inputs_for_run(self, run_id: str) -> None:
        record = self.load_run(run_id)
        upload_dir = Path(record.input_path)
        workspace = self.workspace_for_record(record)
        target_rgb = workspace.images_full_rgb
        target_mapir = workspace.images_full_mapir
        camera_targets = self._camera_targets_for_record(record)
        target_thermal = workspace.images_full_thermal

        def _reset_target(target_dir: Path) -> None:
            target_dir.mkdir(parents=True, exist_ok=True)
            for file_path in target_dir.iterdir():
                if file_path.is_file():
                    file_path.unlink()

        def _copy_inputs(source_dir: Path, target_dir: Path) -> None:
            if not source_dir.exists():
                return
            for src in source_dir.iterdir():
                if src.is_file():
                    shutil.copy2(src, target_dir / src.name)

        _reset_target(target_rgb)
        _reset_target(target_mapir)
        _reset_target(target_thermal)
        if 'rgb' in camera_targets:
            _copy_inputs(upload_dir / 'rgb', target_rgb)
        if 'mapir' in camera_targets:
            _copy_inputs(upload_dir / 'mapir', target_mapir)
        if 'thermal' in camera_targets:
            _copy_inputs(upload_dir / 'thermal', target_thermal)

    def _camera_targets_for_record(self, record: RunRecord) -> set[str]:
        configured = {
            str(item).strip().lower()
            for item in (record.parameters.get('camera_targets') or [])
            if str(item).strip()
        }
        if configured:
            return configured
        source_run_id = record.parameters.get('source_orthophoto_run_id')
        if source_run_id and not record.selected_steps.run_odm:
            source = self.load_run(str(source_run_id))
            restored = {
                key.replace('orthophoto_', '')
                for key in ('orthophoto_rgb', 'orthophoto_mapir', 'orthophoto_thermal')
                if source.outputs.get(key)
            }
            if restored:
                return restored
        return {'rgb', 'mapir'}

    def stage_saved_orthophotos_for_run(self, run_id: str, source_run_id: str) -> None:
        source = self.load_run(source_run_id)
        workspace = self.workspace_for_run(run_id)
        targets = {
            'orthophoto_rgb': workspace.ortho_rgb,
            'orthophoto_mapir': workspace.ortho_mapir,
            'orthophoto_thermal': workspace.ortho_thermal,
        }
        for key, target in targets.items():
            source_path = source.outputs.get(key)
            if not source_path:
                continue
            source_file = Path(source_path)
            if not source_file.exists():
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_file, target)

    def _clear_discoverable_outputs_for_run(self, record: RunRecord) -> None:
        workspace = self.workspace_for_record(record)
        candidate_paths: list[Path] = []

        if not self._is_orthophoto_creation_run(record):
            vegetation_index_root = workspace.vegetation_index_output
            candidate_paths.extend([
                vegetation_index_root / 'vegetation_index.tif',
                vegetation_index_root / 'vegetation_index_color.png',
                vegetation_index_root / 'metadata.json',
                vegetation_index_root / 'vegetation_index_grid_overlay.png',
                vegetation_index_root / 'vegetation_index_grid_cells.csv',
                vegetation_index_root / 'vegetation_index_grid_categories.csv',
                vegetation_index_root / 'grid_metadata.json',
            ])
        if record.selected_steps.run_odm:
            candidate_paths.extend([
                workspace.ortho_rgb,
                workspace.ortho_mapir,
            ])
        if record.selected_steps.generate_report:
            candidate_paths.extend([
                workspace.report_path,
                workspace.output_root / 'report' / 'index.html',
            ])

        for path in candidate_paths:
            if path.exists() and path.is_file():
                path.unlink()

    def ensure_latest_orthophoto_run_saved(self) -> RunRecord | None:
        latest_run = next(
            (
                run
                for run in self.list_runs()
                if run.status == 'completed' and run.selected_steps.run_odm
            ),
            None,
        )
        if latest_run is None:
            return None
        saved_outputs = {
            key: value
            for key, value in latest_run.outputs.items()
            if key in {'orthophoto_rgb', 'orthophoto_mapir', 'orthophoto_thermal'}
            and value
            and Path(value).exists()
            and 'orthophotos' in Path(value).parts
        }
        if saved_outputs:
            return latest_run
        outputs = self._discover_outputs(Path(latest_run.run_dir))
        return self.update_status(latest_run.run_id, outputs=outputs)

    def start_run(self, run_id: str) -> RunRecord:
        record = self.load_run(run_id)
        if run_id in self._threads and self._threads[run_id].is_alive():
            return record
        blocker = self._active_run_blocker(run_id)
        if blocker is not None:
            raise RunStartBlocked(
                f'Another run is already active ({blocker.run_id}). '
                'Wait for it to finish or stop it before starting a new run.'
            )
        self._cancel_events[run_id] = threading.Event()
        record = self.update_status(
            run_id,
            status='running',
            current_stage='queued',
            stage_message='Starting pipeline',
            progress_percent=0,
            errors=[],
        )
        thread = threading.Thread(target=self._execute_run, args=(run_id,), daemon=True, name=f'agrivision-run-{run_id}')
        self._threads[run_id] = thread
        thread.start()
        return record

    def _as_positive_int(self, value: object, fallback: int) -> int:
        try:
            return max(1, int(value))
        except (TypeError, ValueError):
            return fallback

    def request_stop(self, run_id: str) -> RunRecord:
        record = self.load_run(run_id)
        if record.status not in {'queued', 'running'}:
            return record

        event = self._cancel_events.setdefault(run_id, threading.Event())
        event.set()
        self._stop_odm_containers()
        return self.finalize_run_status(
            run_id,
            status='cancelled',
            current_stage='cancelled',
            stage_message='Run stopped by operator.',
            error_message='Run stopped by operator.',
            running_stage_state='cancelled',
            running_stage_message='Stopped by operator.',
        )

    def launch_run(self, run_id: str) -> RunRecord:
        self._cancel_events[run_id] = threading.Event()
        self._execute_run(run_id)
        return self.load_run(run_id)

    def _raise_if_cancelled(self, run_id: str) -> None:
        if self._cancel_events.get(run_id, threading.Event()).is_set():
            raise RunCancelled('Run stopped by operator.')

    def _stop_odm_containers(self) -> None:
        for container_name in ('agrivision-odm-rgb', 'agrivision-odm-mapir', 'agrivision-odm-thermal'):
            with contextlib.suppress(FileNotFoundError):
                subprocess.run(
                    ['docker', 'stop', container_name],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )

    def _execute_run(self, run_id: str) -> None:
        record = self.load_run(run_id)
        started_at = datetime.now(timezone.utc)
        self.update_status(run_id, status='running', started_at=started_at, current_stage='stage_inputs', stage_message='Staging inputs', progress_percent=0)
        log_path = Path(record.logs_path)
        try:
            self._raise_if_cancelled(run_id)
            self.update_stage(run_id, 'stage_inputs', 'running', 'Staging MAPIR and RGB inputs')
            self._clear_discoverable_outputs_for_run(record)
            self.update_stage(run_id, 'stage_inputs', 'running', 'Staging camera inputs')
            self._clear_discoverable_outputs_for_run(record)
            self.stage_inputs_for_run(run_id)
            source_orthophoto_run_id = record.parameters.get('source_orthophoto_run_id')
            if source_orthophoto_run_id and not record.selected_steps.run_odm:
                self.stage_saved_orthophotos_for_run(run_id, str(source_orthophoto_run_id))
            self.update_stage(run_id, 'stage_inputs', 'completed', 'Inputs staged')
            self._raise_if_cancelled(run_id)

            selected = record.selected_steps
            orthophoto_creation_only = self._is_orthophoto_creation_run(record)
            camera_targets = set(record.parameters.get('camera_targets') or ['rgb', 'mapir'])
            def callback(stage_key: str, message: str, state: str = 'running') -> None:
                self._raise_if_cancelled(run_id)
                self.update_stage(run_id, stage_key, state, message)

            with log_path.open('a', encoding='utf-8') as log_handle:
                with contextlib.redirect_stdout(log_handle), contextlib.redirect_stderr(log_handle):
                    run_full_pipeline(
                        skip_odm=not selected.run_odm,
                        skip_odm_rgb='rgb' not in camera_targets,
                        skip_odm_mapir='mapir' not in camera_targets,
                        skip_odm_thermal='thermal' not in camera_targets,
                        skip_vegetation_index=orthophoto_creation_only,
                        skip_grid=orthophoto_creation_only,
                        skip_weather=not selected.fetch_weather,
                        skip_irrigation=not selected.run_irrigation,
                        skip_pdm=not selected.run_pdm,
                        skip_report=not selected.generate_report,
                        orthophoto_resolution_cm=record.parameters.get('orthophoto_resolution_cm'),
                        pdm_crop=record.parameters.get('pdm_crop'),
                        pdm_model_key=record.parameters.get('pdm_model_key'),
                        progress_callback=callback,
                        workspace_root=self.workspace_for_record(record).root,
                        config=self.workspace_for_record(record).config,
                    )
            self._raise_if_cancelled(run_id)
            outputs = self._discover_outputs(Path(record.run_dir))
            self.finalize_run_status(
                run_id,
                status='completed',
                outputs=outputs,
                errors=[],
                progress_percent=100,
                current_stage='completed',
                stage_message='Pipeline completed',
            )
        except RunCancelled as exc:
            self.finalize_run_status(
                run_id,
                status='cancelled',
                current_stage='cancelled',
                stage_message=str(exc),
                error_message=str(exc),
                running_stage_state='cancelled',
                running_stage_message='Stopped by operator.',
            )
            with log_path.open('a', encoding='utf-8') as log_handle:
                log_handle.write(f"\n[dashboard] Run cancelled: {exc}\n")
        except Exception as exc:
            if self._cancel_events.get(run_id, threading.Event()).is_set():
                self.finalize_run_status(
                    run_id,
                    status='cancelled',
                    current_stage='cancelled',
                    stage_message='Run stopped by operator.',
                    error_message='Run stopped by operator.',
                    running_stage_state='cancelled',
                    running_stage_message='Stopped by operator.',
                )
                with log_path.open('a', encoding='utf-8') as log_handle:
                    log_handle.write(f"\n[dashboard] Run cancelled: {exc}\n")
                return
            outputs = self._discover_outputs(Path(record.run_dir))
            raw_error = str(exc)
            summary = summarize_failure(raw_error)
            failed_record = self.update_stage(run_id, self.load_run(run_id).current_stage or 'pipeline', 'failed', summary)
            self.finalize_run_status(
                run_id,
                status='failed',
                outputs=outputs,
                current_stage=failed_record.current_stage,
                stage_message=summary,
                error_message=summary,
                running_stage_state='failed',
                running_stage_message=summary,
            )
            with log_path.open('a', encoding='utf-8') as log_handle:
                log_handle.write(f"\n[dashboard] Run failed: {summary}\n")
                if raw_error != summary:
                    log_handle.write(f"[dashboard] Raw error: {raw_error}\n")
        finally:
            self._cancel_events.pop(run_id, None)

    def _report_filename_for_run(self, record: RunRecord) -> str:
        base_name = record.run_name.strip() if record.run_name else _timestamp_report_name()
        return f"{_slugify_report_name(base_name)}.html"

    def _persist_report_for_run(self, record: RunRecord, source_report: Path) -> Path:
        run_output_dir = self._run_output_dir(record.run_id)
        run_output_dir.mkdir(parents=True, exist_ok=True)
        destination = run_output_dir / self._report_filename_for_run(record)
        shutil.copy2(source_report, destination)
        return destination

    def _persist_output_for_run(self, record: RunRecord, source_path: Path, filename: str) -> Path:
        run_output_dir = self._run_orthophoto_output_dir(record.run_id)
        run_output_dir.mkdir(parents=True, exist_ok=True)
        destination = run_output_dir / filename
        shutil.copy2(source_path, destination)
        return destination

    def _artifact_stage(self, record: RunRecord, key: str) -> str:
        if key == 'report_html':
            return 'generate_report'
        if key == 'disease_risk_summary':
            return 'disease_risk'
        if key.startswith('orthophoto_'):
            if record.parameters.get('source_orthophoto_run_id') and not record.selected_steps.run_odm:
                return 'stage_inputs'
            if key == 'orthophoto_mapir':
                return 'run_odm_mapir'
            if key == 'orthophoto_thermal':
                return 'run_odm_thermal'
            return 'run_odm_rgb'
        if key.startswith('grid_'):
            return 'generate_grid'
        return 'compute_vegetation_index'

    def _artifact_source_path(self, record: RunRecord, key: str, discovered_path: Path) -> Path:
        source_run_id = record.parameters.get('source_orthophoto_run_id')
        if key.startswith('orthophoto_') and source_run_id and not record.selected_steps.run_odm:
            source = self.load_run(str(source_run_id))
            source_path = source.outputs.get(key)
            if source_path:
                return Path(source_path)
        return discovered_path

    def _artifact_origin(self, record: RunRecord, key: str, stored_path: Path, source_path: Path) -> str:
        if key.startswith('orthophoto_') and record.parameters.get('source_orthophoto_run_id') and not record.selected_steps.run_odm:
            return 'restored_from_previous_run'
        if stored_path != source_path:
            return 'copied_from_workspace'
        return 'generated_in_run_workspace'

    def _artifact_record(
        self,
        record: RunRecord,
        key: str,
        *,
        stored_path: Path,
        discovered_path: Path,
        discovered_at: datetime,
    ) -> ArtifactRecord:
        source_path = self._artifact_source_path(record, key, discovered_path)
        source_run_id = record.parameters.get('source_orthophoto_run_id')
        return ArtifactRecord(
            stored_path=str(stored_path),
            source_path=str(source_path),
            stage=self._artifact_stage(record, key),
            origin=self._artifact_origin(record, key, stored_path, source_path),
            discovered_at=discovered_at,
            source_run_id=(
                str(source_run_id)
                if key.startswith('orthophoto_') and source_run_id and not record.selected_steps.run_odm
                else None
            ),
        )

    def _discover_outputs_with_artifacts(self, run_dir: Path) -> tuple[dict[str, str], dict[str, ArtifactRecord]]:
        record = RunRecord.model_validate(self.storage.read_json(run_dir / 'status.json'))
        workspace = self.workspace_for_record(record)
        selected = record.selected_steps
        camera_targets = self._camera_targets_for_record(record)
        report_candidates = [
            workspace.report_path,
            workspace.output_root / 'report' / 'index.html',
        ]
        include_orthophotos = selected.run_odm or bool(record.parameters.get('source_orthophoto_run_id'))
        candidates = {
            **(
                {
                    'vegetation_index_tif': workspace.vegetation_index_output / 'vegetation_index.tif',
                    'vegetation_index_metadata': workspace.vegetation_index_output / 'metadata.json',
                    'grid_metadata': workspace.vegetation_index_output / 'grid_metadata.json',
                    'disease_risk_summary': workspace.vegetation_index_output / 'disease_risk' / 'summary.json',
                    'vegetation_index_color_png': workspace.vegetation_index_output / 'vegetation_index_color.png',
                    'grid_overlay_png': workspace.vegetation_index_output / 'vegetation_index_grid_overlay.png',
                    'grid_cells_csv': workspace.vegetation_index_output / 'vegetation_index_grid_cells.csv',
                    'grid_categories_csv': workspace.vegetation_index_output / 'vegetation_index_grid_categories.csv',
                }
                if not self._is_orthophoto_creation_run(record)
                else {}
            ),
            **(
                {
                    **({'orthophoto_rgb': workspace.ortho_rgb} if 'rgb' in camera_targets else {}),
                    **({'orthophoto_mapir': workspace.ortho_mapir} if 'mapir' in camera_targets else {}),
                    **({'orthophoto_thermal': workspace.ortho_thermal} if 'thermal' in camera_targets else {}),
                }
                if include_orthophotos
                else {}
            ),
        }

        discovered_at = datetime.now(timezone.utc)
        outputs: dict[str, str] = {}
        artifacts: dict[str, ArtifactRecord] = {}
        for name, path in candidates.items():
            if not path.exists():
                continue
            stored_path = path
            if name == 'orthophoto_rgb':
                stored_path = self._persist_output_for_run(record, path, 'orthophoto_rgb.tif')
            elif name == 'orthophoto_mapir':
                stored_path = self._persist_output_for_run(record, path, 'orthophoto_mapir.tif')
            elif name == 'orthophoto_thermal':
                stored_path = self._persist_output_for_run(record, path, 'orthophoto_thermal.tif')
            outputs[name] = str(stored_path)
            artifacts[name] = self._artifact_record(
                record,
                name,
                stored_path=stored_path,
                discovered_path=path,
                discovered_at=discovered_at,
            )
        report_path = next((path for path in report_candidates if path.exists()), None)
        if selected.generate_report and report_path is not None:
            stored_report = self._persist_report_for_run(record, report_path)
            outputs['report_html'] = str(stored_report)
            artifacts['report_html'] = self._artifact_record(
                record,
                'report_html',
                stored_path=stored_report,
                discovered_path=report_path,
                discovered_at=discovered_at,
            )
        return outputs, artifacts

    def _discover_outputs(self, run_dir: Path) -> dict[str, str]:
        outputs, artifacts = self._discover_outputs_with_artifacts(run_dir)
        self.storage.write_json(run_dir / 'outputs.json', outputs)
        self.storage.write_json(run_dir / 'artifacts.json', {key: value.model_dump(mode='json') for key, value in artifacts.items()})
        self.update_status(run_id=Path(run_dir).name, outputs=outputs, artifacts=artifacts)
        return outputs

    def log_text(self, run_id: str) -> str:
        record = self.load_run(run_id)
        log_path = Path(record.logs_path)
        if not log_path.exists():
            log_path = self.storage.run_dir(run_id) / 'run.log'
        if not log_path.exists():
            return ''
        return log_path.read_text(encoding='utf-8')[-10000:]
