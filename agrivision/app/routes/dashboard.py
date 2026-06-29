from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from agrivision.app import dependencies as deps
from agrivision.app.formatters import step_summary
from agrivision.app.health import service_health
from agrivision.services.service_control import missing_service_repos

router = APIRouter()


@router.get('/health')
def health() -> dict[str, str]:
    return {'status': 'ok'}


@router.get('/', response_class=HTMLResponse)
def dashboard(request: Request) -> HTMLResponse:
    runs = deps.run_service.list_runs()
    status_summary: dict[str, int] = {}
    for run in runs:
        status_summary[run.status] = status_summary.get(run.status, 0) + 1
    latest_report = deps.report_service.latest_report(generate_preview=False)
    active_runs = sum(1 for run in runs if run.status in {'queued', 'running'})
    return deps.templates.TemplateResponse(
        request,
        'dashboard.html',
        {
            'recent_runs': runs[:10],
            'total_runs': len(runs),
            'active_runs': active_runs,
            'status_summary': status_summary,
            'latest_report': latest_report,
            'service_health': service_health(),
            'missing_services': missing_service_repos(),
            'step_summary': step_summary,
        },
    )
