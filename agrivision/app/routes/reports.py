from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from agrivision.app import dependencies as deps

router = APIRouter()


@router.get('/reports')
def reports(request: Request):
    report_items = deps.report_service.list_reports(generate_previews=False)
    if 'text/html' in request.headers.get('accept', ''):
        return deps.templates.TemplateResponse(request, 'reports.html', {'reports': report_items})
    return [item.model_dump(mode='json') for item in report_items]


@router.get('/reports/{run_id}')
def get_report(run_id: str) -> dict:
    return deps.report_service.get_report(run_id).model_dump(mode='json')


@router.get('/reports/{run_id}/view', response_class=HTMLResponse)
def report_view(run_id: str, request: Request, embedded: bool = False) -> HTMLResponse:
    report = deps.report_service.get_report(run_id)
    if not report.report_path:
        raise HTTPException(status_code=404, detail='Report not found.')
    run = deps.run_service.load_run(run_id)
    template_name = 'report_embed.html' if embedded else 'report_view.html'
    return deps.templates.TemplateResponse(
        request,
        template_name,
        {'run': run, 'report': report},
    )
