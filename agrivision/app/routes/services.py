from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from agrivision.app import dependencies as deps
from agrivision.services.service_control import ensure_service, restart_service, service_statuses

router = APIRouter()


@router.get('/services', response_class=HTMLResponse)
def services_page(request: Request) -> HTMLResponse:
    return deps.templates.TemplateResponse(
        request,
        'services.html',
        {'services': service_statuses(include_logs=True), 'message': None},
    )


@router.get('/services/status')
def services_status() -> list[dict[str, object]]:
    return service_statuses(include_logs=False)


@router.post('/ui/services/{service_key}/start')
def start_service_ui(service_key: str) -> RedirectResponse:
    if service_key not in {'weather', 'irrigation', 'pdm'}:
        raise HTTPException(status_code=404, detail='Service not found.')
    try:
        ensure_service(service_key, timeout_seconds=90)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return RedirectResponse(url='/services', status_code=303)


@router.post('/ui/services/{service_key}/restart')
def restart_service_ui(service_key: str) -> RedirectResponse:
    if service_key not in {'weather', 'irrigation', 'pdm'}:
        raise HTTPException(status_code=404, detail='Service not found.')
    try:
        restart_service(service_key, timeout_seconds=90)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return RedirectResponse(url='/services', status_code=303)
