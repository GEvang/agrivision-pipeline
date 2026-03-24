from __future__ import annotations

from pathlib import Path

from agrivision.app.schemas.runs import ReportItem, RunRecord
from agrivision.services.preview_service import PreviewService
from agrivision.services.run_service import RunService


class ReportService:
    def __init__(self, run_service: RunService | None = None, preview_service: PreviewService | None = None) -> None:
        self.run_service = run_service or RunService()
        self.preview_service = preview_service or PreviewService()

    def list_reports(self) -> list[ReportItem]:
        reports: list[ReportItem] = []
        for run in self.run_service.list_runs():
            reports.append(self._to_report_item(run))
        return reports

    def get_report(self, run_id: str) -> ReportItem:
        return self._to_report_item(self.run_service.load_run(run_id))

    def _to_report_item(self, run: RunRecord) -> ReportItem:
        preview_path: str | None = None
        orthophoto_path = run.outputs.get('orthophoto_rgb') or run.outputs.get('orthophoto_mapir')
        if orthophoto_path:
            artifact = Path(orthophoto_path)
            preview_file = Path(run.run_dir) / 'previews' / self.preview_service.preview_name_for(artifact)
            generated = self.preview_service.ensure_preview(artifact, preview_file)
            preview_path = str(generated) if generated else None
        return ReportItem(
            run_id=run.run_id,
            created_at=run.created_at,
            dataset_name=run.dataset_name,
            status=run.status,
            report_path=run.outputs.get('report_html'),
            orthophoto_path=orthophoto_path,
            preview_path=preview_path,
        )
