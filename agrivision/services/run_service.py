from __future__ import annotations

import contextlib
import re
import shutil
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path

from agrivision.app.schemas.runs import RunCreateRequest, RunRecord, StageStatus
from agrivision.config import get_project_root, load_config
from agrivision.pipeline.orchestrator import run_full_pipeline
from agrivision.services.storage_service import StorageService


def _slugify_report_name(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", value.strip()).strip("-").lower()
    return slug or "report"


def _timestamp_report_name() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


class RunCancelled(RuntimeError):
    pass


class RunService:
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

    def _build_stages(self, selected_steps) -> list[StageStatus]:
        stages = [StageStatus(key='stage_inputs', label='Stage inputs')]
        if selected_steps.resize_images:
            stages.append(StageStatus(key='resize_images', label='Resize images'))
        if selected_steps.run_odm:
            stages.extend([
                StageStatus(key='run_odm_rgb', label='Run ODM RGB'),
                StageStatus(key='run_odm_mapir', label='Run ODM MAPIR'),
            ])
        stages.extend([
            StageStatus(key='compute_ndvi', label='Compute NDVI'),
            StageStatus(key='generate_grid', label='Generate grid'),
        ])
        if selected_steps.fetch_weather:
            stages.append(StageStatus(key='fetch_weather', label='Fetch weather'))
        stages.append(StageStatus(key='irrigation_enrichment', label='Irrigation enrichment'))
        if selected_steps.run_pdm:
            stages.append(StageStatus(key='pdm_enrichment', label='Pest & disease enrichment'))
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
        Path(record.logs_path).touch(exist_ok=True)

    def load_run(self, run_id: str) -> RunRecord:
        path = self.storage.run_dir(run_id) / 'status.json'
        return RunRecord.model_validate(self.storage.read_json(path))

    def list_runs(self) -> list[RunRecord]:
        runs: list[RunRecord] = []
        for status_path in sorted(self.storage.layout.runs_root.glob('*/status.json'), reverse=True):
            try:
                runs.append(RunRecord.model_validate(self.storage.read_json(status_path)))
            except Exception:
                continue
        runs.sort(key=lambda item: item.created_at, reverse=True)
        return runs

    def update_status(
        self,
        run_id: str,
        *,
        status: str | None = None,
        outputs: dict[str, str] | None = None,
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

    def stage_inputs_for_run(self, run_id: str) -> None:
        record = self.load_run(run_id)
        config = load_config()
        project_root = get_project_root()
        upload_dir = Path(record.input_path)
        target_rgb = project_root / config['paths']['images_full']
        target_mapir = project_root / config['paths']['images_full_mapir']

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
        _copy_inputs(upload_dir / 'rgb', target_rgb)
        _copy_inputs(upload_dir / 'mapir', target_mapir)

    def start_run(self, run_id: str) -> RunRecord:
        record = self.load_run(run_id)
        if run_id in self._threads and self._threads[run_id].is_alive():
            return record
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

    def request_stop(self, run_id: str) -> RunRecord:
        record = self.load_run(run_id)
        if record.status not in {'queued', 'running'}:
            return record

        event = self._cancel_events.setdefault(run_id, threading.Event())
        event.set()
        self._stop_odm_containers()
        stages = [StageStatus.model_validate(stage.model_dump()) for stage in record.stages]
        for stage in stages:
            if stage.state == 'running':
                stage.state = 'failed'
                stage.message = 'Stopped by operator'
            elif stage.state == 'pending':
                stage.state = 'skipped'
        return self.update_status(
            run_id,
            status='cancelled',
            current_stage=record.current_stage,
            stage_message='Run stopped by operator.',
            errors=[*record.errors, 'Run stopped by operator.'],
            finished_at=datetime.now(timezone.utc),
            stages=stages,
        )

    def launch_run(self, run_id: str) -> RunRecord:
        self._cancel_events[run_id] = threading.Event()
        self._execute_run(run_id)
        return self.load_run(run_id)

    def _raise_if_cancelled(self, run_id: str) -> None:
        if self._cancel_events.get(run_id, threading.Event()).is_set():
            raise RunCancelled('Run stopped by operator.')

    def _stop_odm_containers(self) -> None:
        for container_name in ('agrivision-odm-rgb', 'agrivision-odm-mapir'):
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
            self.stage_inputs_for_run(run_id)
            self.update_stage(run_id, 'stage_inputs', 'completed', 'Inputs staged')
            self._raise_if_cancelled(run_id)

            selected = record.selected_steps
            def callback(stage_key: str, message: str, state: str = 'running') -> None:
                self._raise_if_cancelled(run_id)
                self.update_stage(run_id, stage_key, state, message)

            with log_path.open('a', encoding='utf-8') as log_handle:
                with contextlib.redirect_stdout(log_handle), contextlib.redirect_stderr(log_handle):
                    run_full_pipeline(
                        run_resize_step=selected.resize_images,
                        skip_odm=not selected.run_odm,
                        skip_weather=not selected.fetch_weather,
                        skip_pdm=not selected.run_pdm,
                        skip_report=not selected.generate_report,
                        pdm_crop=record.parameters.get('pdm_crop'),
                        pdm_model_key=record.parameters.get('pdm_model_key'),
                        progress_callback=callback,
                    )
            self._raise_if_cancelled(run_id)
            outputs = self._discover_outputs(Path(record.run_dir))
            self.update_status(
                run_id,
                status='completed',
                outputs=outputs,
                errors=[],
                progress_percent=100,
                current_stage='completed',
                stage_message='Pipeline completed',
                finished_at=datetime.now(timezone.utc),
            )
        except RunCancelled as exc:
            record = self.load_run(run_id)
            self.update_status(
                run_id,
                status='cancelled',
                errors=[*record.errors, str(exc)] if str(exc) not in record.errors else record.errors,
                finished_at=datetime.now(timezone.utc),
                stage_message=str(exc),
            )
            with log_path.open('a', encoding='utf-8') as log_handle:
                log_handle.write(f"\n[dashboard] Run cancelled: {exc}\n")
        except Exception as exc:
            if self._cancel_events.get(run_id, threading.Event()).is_set():
                record = self.load_run(run_id)
                self.update_status(
                    run_id,
                    status='cancelled',
                    errors=[*record.errors, 'Run stopped by operator.'],
                    finished_at=datetime.now(timezone.utc),
                    stage_message='Run stopped by operator.',
                )
                with log_path.open('a', encoding='utf-8') as log_handle:
                    log_handle.write(f"\n[dashboard] Run cancelled: {exc}\n")
                return
            outputs = self._discover_outputs(Path(record.run_dir))
            self.update_stage(run_id, self.load_run(run_id).current_stage or 'pipeline', 'failed', str(exc))
            self.update_status(
                run_id,
                status='failed',
                outputs=outputs,
                errors=[str(exc)],
                finished_at=datetime.now(timezone.utc),
                stage_message=str(exc),
            )
            with log_path.open('a', encoding='utf-8') as log_handle:
                log_handle.write(f"\n[dashboard] Run failed: {exc}\n")
        finally:
            self._cancel_events.pop(run_id, None)

    def _report_filename_for_run(self, record: RunRecord) -> str:
        base_name = record.run_name.strip() if record.run_name else _timestamp_report_name()
        return f"{_slugify_report_name(base_name)}.html"

    def _persist_report_for_run(self, record: RunRecord, source_report: Path) -> Path:
        config = load_config()
        runs_output_root = self.storage.layout.project_root / config['paths'].get('runs_output', 'output/runs')
        run_output_dir = runs_output_root / record.run_id
        run_output_dir.mkdir(parents=True, exist_ok=True)
        destination = run_output_dir / self._report_filename_for_run(record)
        shutil.copy2(source_report, destination)
        return destination

    def _discover_outputs(self, run_dir: Path) -> dict[str, str]:
        config = load_config()
        project_root = self.storage.layout.project_root
        record = RunRecord.model_validate(self.storage.read_json(run_dir / 'status.json'))
        report_candidates = [
            project_root / config['paths']['output_root'] / 'report_latest.html',
            project_root / config['paths']['output_root'] / 'report' / 'index.html',
        ]
        candidates = {
            'ndvi_tif': project_root / config['paths']['ndvi_output'] / 'ndvi.tif',
            'orthophoto_rgb': project_root / config['paths']['odm_project_root_rgb'] / 'project' / 'odm_orthophoto' / 'odm_orthophoto.tif',
            'orthophoto_mapir': project_root / config['paths']['odm_project_root_mapir'] / 'project' / 'odm_orthophoto' / 'odm_orthophoto.tif',
        }
        outputs = {name: str(path) for name, path in candidates.items() if path.exists()}
        report_path = next((path for path in report_candidates if path.exists()), None)
        if report_path is not None:
            outputs['report_html'] = str(self._persist_report_for_run(record, report_path))
        self.storage.write_json(run_dir / 'outputs.json', outputs)
        return outputs

    def log_text(self, run_id: str) -> str:
        record = self.load_run(run_id)
        log_path = Path(record.logs_path)
        if not log_path.exists():
            log_path = self.storage.run_dir(run_id) / 'run.log'
        if not log_path.exists():
            return ''
        return log_path.read_text(encoding='utf-8')[-10000:]
