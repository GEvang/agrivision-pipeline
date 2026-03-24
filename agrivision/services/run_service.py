from __future__ import annotations

import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from agrivision.app.schemas.runs import RunCreateRequest, RunRecord
from agrivision.config import get_project_root, load_config
from agrivision.services.storage_service import StorageService


class RunService:
    def __init__(self, storage: StorageService | None = None) -> None:
        self.storage = storage or StorageService()

    def create_run_record(self, request: RunCreateRequest) -> RunRecord:
        run_id = self.storage.new_run_id()
        run_dir = self.storage.run_dir(run_id)
        upload_dir = self.storage.upload_dir(request.upload_run_id)
        created_at = datetime.now(timezone.utc)
        record = RunRecord(
            run_id=run_id,
            created_at=created_at,
            updated_at=created_at,
            dataset_name=request.dataset_name,
            input_path=str(upload_dir),
            status='queued',
            selected_steps=request.selected_steps,
            parameters={
                'preset': request.parameters.preset,
                'notes': request.parameters.notes,
                'flight_date': request.parameters.flight_date.isoformat() if request.parameters.flight_date else None,
            },
            outputs={},
            errors=[],
            logs_path=str(run_dir / 'run.log'),
            run_name=request.run_name,
            field_name=request.field_name,
            run_dir=str(run_dir),
        )
        self._write_record_files(record)
        return record

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

    def update_status(self, run_id: str, *, status: str, outputs: dict[str, str] | None = None, errors: list[str] | None = None) -> RunRecord:
        record = self.load_run(run_id)
        record.status = status  # type: ignore[misc]
        record.updated_at = datetime.now(timezone.utc)
        if outputs is not None:
            record.outputs = outputs
            self.storage.write_json(Path(record.run_dir) / 'outputs.json', outputs)
        if errors is not None:
            record.errors = errors
        self.storage.write_json(Path(record.run_dir) / 'status.json', record.model_dump(mode='json'))
        return record

    def stage_inputs_for_run(self, run_id: str) -> None:
        record = self.load_run(run_id)
        config = load_config()
        project_root = get_project_root()
        upload_dir = Path(record.input_path)
        target_rgb = project_root / config['paths']['images_full']
        target_rgb.mkdir(parents=True, exist_ok=True)
        for file_path in target_rgb.iterdir():
            if file_path.is_file():
                file_path.unlink()
        for src in upload_dir.iterdir():
            if src.is_file():
                shutil.copy2(src, target_rgb / src.name)

    def launch_run(self, run_id: str) -> RunRecord:
        record = self.load_run(run_id)
        self.stage_inputs_for_run(run_id)
        run_dir = Path(record.run_dir)
        log_path = Path(record.logs_path)
        args = [sys.executable, '-m', 'agrivision.app.cli']
        if record.selected_steps.resize_images:
            args.append('--run-resize')
        if not record.selected_steps.run_odm or not record.selected_steps.generate_orthophoto:
            args.append('--skip-odm')
        if not record.selected_steps.fetch_weather:
            args.append('--skip-weather')
        if not record.selected_steps.generate_report:
            args.append('--skip-report')

        env = os.environ.copy()
        env['AGRIVISION_ACTIVE_RUN_ID'] = run_id
        with log_path.open('a', encoding='utf-8') as log_handle:
            result = subprocess.run(
                args,
                cwd=str(self.storage.layout.project_root),
                env=env,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                check=False,
            )
        outputs = self._discover_outputs(run_dir)
        final_status = 'completed' if result.returncode == 0 else 'failed'
        errors = [] if final_status == 'completed' else ['Pipeline finished without expected outputs. Review run.log.']
        return self.update_status(run_id, status=final_status, outputs=outputs, errors=errors)

    def _discover_outputs(self, run_dir: Path) -> dict[str, str]:
        config = load_config()
        project_root = self.storage.layout.project_root
        candidates = {
            'report_html': project_root / config['paths']['output_root'] / 'report' / 'index.html',
            'ndvi_tif': project_root / config['paths']['ndvi_output'] / 'ndvi.tif',
            'orthophoto_rgb': project_root / config['paths']['odm_project_root_rgb'] / 'project' / 'odm_orthophoto' / 'odm_orthophoto.tif',
            'orthophoto_mapir': project_root / config['paths']['odm_project_root_mapir'] / 'project' / 'odm_orthophoto' / 'odm_orthophoto.tif',
        }
        outputs = {name: str(path) for name, path in candidates.items() if path.exists()}
        self.storage.write_json(run_dir / 'outputs.json', outputs)
        return outputs

    def log_text(self, run_id: str) -> str:
        record = self.load_run(run_id)
        log_path = Path(record.logs_path)
        if not log_path.exists():
            return ''
        return log_path.read_text(encoding='utf-8')[-10000:]
