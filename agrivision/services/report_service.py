from __future__ import annotations

from pathlib import Path

from agrivision.app.schemas.runs import ReportItem, RunRecord
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
        )
