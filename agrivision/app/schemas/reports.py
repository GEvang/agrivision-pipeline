from __future__ import annotations

from pydantic import BaseModel

from agrivision.app.schemas.runs import ReportItem, RunRecord


class DashboardView(BaseModel):
    recent_runs: list[RunRecord]
    status_summary: dict[str, int]
    latest_report: ReportItem | None = None


class ReportsView(BaseModel):
    reports: list[ReportItem]
