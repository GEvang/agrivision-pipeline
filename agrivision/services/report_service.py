from __future__ import annotations

from pathlib import Path
from typing import Any

from agrivision.app.schemas.runs import ReportItem, RunRecord
from agrivision.config import get_project_root, load_config
from agrivision.services.preview_service import PreviewService
from agrivision.services.run_service import RunService


class ReportService:
    def __init__(self, run_service: RunService | None = None, preview_service: PreviewService | None = None) -> None:
        self.run_service = run_service or RunService()
        self.preview_service = preview_service or PreviewService()

    def list_reports(self, *, generate_previews: bool = True, limit: int | None = None) -> list[ReportItem]:
        reports: list[ReportItem] = []
        for run in self.run_service.list_runs():
            reports.append(self._to_report_item(run, generate_preview=generate_previews))
            if limit is not None and len(reports) >= limit:
                break
        return reports

    def latest_report(self, *, generate_preview: bool = False) -> ReportItem | None:
        for run in self.run_service.list_runs():
            item = self._to_report_item(run, generate_preview=generate_preview)
            if item.report_path:
                return item
        return None

    def get_report(self, run_id: str, *, generate_preview: bool = True) -> ReportItem:
        return self._to_report_item(self.run_service.load_run(run_id), generate_preview=generate_preview)

    def _to_report_item(self, run: RunRecord, *, generate_preview: bool = True) -> ReportItem:
        preview_path: str | None = None
        orthophoto_path = run.outputs.get('orthophoto_rgb') or run.outputs.get('orthophoto_mapir')
        if orthophoto_path and generate_preview:
            artifact = Path(orthophoto_path)
            preview_file = Path(run.run_dir) / 'previews' / self.preview_service.preview_name_for(artifact)
            generated = self.preview_service.ensure_preview(artifact, preview_file)
            preview_path = str(generated) if generated else None
        return ReportItem(
            run_id=run.run_id,
            created_at=run.created_at,
            run_name=run.run_name,
            dataset_name=run.dataset_name,
            status=run.status,
            report_path=run.outputs.get('report_html'),
            orthophoto_path=orthophoto_path,
            preview_path=preview_path,
            quality=self._quality_summary(run),
        )

    def _quality_summary(self, run: RunRecord) -> dict[str, Any]:
        ndvi_meta = self._read_json(self._metadata_path(run, 'ndvi_metadata', 'metadata.json'))
        grid_meta = self._read_json(self._metadata_path(run, 'grid_metadata', 'grid_metadata.json'))
        if not ndvi_meta and not grid_meta:
            return {}

        valid_pixels = ndvi_meta.get('valid_pixels', {}) if isinstance(ndvi_meta, dict) else {}
        distribution = ndvi_meta.get('distribution', {}) if isinstance(ndvi_meta, dict) else {}
        source = ndvi_meta.get('source', {}) if isinstance(ndvi_meta, dict) else {}
        index = ndvi_meta.get('index', {}) if isinstance(ndvi_meta, dict) else {}
        flags = ndvi_meta.get('quality_flags', []) if isinstance(ndvi_meta, dict) else []
        thresholds_used = grid_meta.get('thresholds_used', {}) if isinstance(grid_meta, dict) else {}
        valid_percent = self._as_float(valid_pixels.get('percent'))
        saturated_high = self._as_float(distribution.get('saturated_high_percent'))
        saturated_low = self._as_float(distribution.get('saturated_low_percent'))
        quality_flags = [str(item) for item in flags if str(item).strip()]
        state = 'ok'
        if quality_flags:
            state = 'warn'
        if valid_percent is not None and valid_percent < 20:
            state = 'error'
            quality_flags.append('Very low valid vegetation-index coverage.')
        elif valid_percent is not None and valid_percent < 50:
            state = 'warn'
            quality_flags.append('Low valid vegetation-index coverage.')
        if saturated_high is not None and saturated_high > 5:
            state = 'warn'
            quality_flags.append('High positive saturation in vegetation-index output.')
        if saturated_low is not None and saturated_low > 5:
            state = 'warn'
            quality_flags.append('High negative saturation in vegetation-index output.')

        return {
            'state': state,
            'source_dataset': source.get('dataset'),
            'index_name': index.get('index_name'),
            'index_mode': index.get('index_mode'),
            'valid_percent': valid_percent,
            'mean': self._as_float(distribution.get('mean')),
            'median': self._as_float(distribution.get('median')),
            'saturated_high_percent': saturated_high,
            'saturated_low_percent': saturated_low,
            'classification_mode': grid_meta.get('classification_mode') if isinstance(grid_meta, dict) else None,
            'poor_max': self._as_float(thresholds_used.get('poor_max')),
            'medium_max': self._as_float(thresholds_used.get('medium_max')),
            'flags': list(dict.fromkeys(quality_flags)),
        }

    def _metadata_path(self, run: RunRecord, output_key: str, filename: str) -> Path:
        configured = run.outputs.get(output_key)
        if configured:
            return Path(configured)
        config = load_config()
        return get_project_root() / config['paths'].get('ndvi_output', 'output/ndvi') / filename

    def _read_json(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        try:
            import json
            payload = json.loads(path.read_text(encoding='utf-8'))
        except Exception:
            return {}
        return payload if isinstance(payload, dict) else {}

    def _as_float(self, value: Any) -> float | None:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
