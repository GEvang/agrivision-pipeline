from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from agrivision.app import dependencies as deps
from agrivision.app.schemas.settings import CredentialsUpdateRequest, SettingsUpdateRequest

router = APIRouter()


@router.get('/settings')
def settings_page(request: Request):
    view = deps.settings_service.get_settings_view()
    if 'text/html' in request.headers.get('accept', ''):
        return deps.templates.TemplateResponse(request, 'settings.html', view)
    return view


@router.post('/settings')
def update_settings(request: SettingsUpdateRequest) -> dict:
    return deps.settings_service.update_non_secret_settings(request)


@router.post('/settings/credentials')
def update_credentials(request: CredentialsUpdateRequest) -> dict:
    return deps.settings_service.update_credentials(request)


@router.post('/ui/settings')
def update_settings_ui(
    location_name: str = Form(''),
    location_lat: float | None = Form(None),
    location_lon: float | None = Form(None),
    weather_base_url: str = Form(''),
    irrigation_base_url: str = Form(''),
    pdm_base_url: str = Form(''),
    pdm_enabled_by_default: bool = Form(False),
    pdm_default_crop: str = Form('grapevine'),
    pdm_default_model_key: str = Form('grapevine_powdery_mildew_risk_v1'),
    resize_max_long_edge: int | None = Form(None),
    orthophoto_resolution_cm: int | None = Form(None),
) -> RedirectResponse:
    update_settings(
        SettingsUpdateRequest(
            location_name=location_name or None,
            location_lat=location_lat,
            location_lon=location_lon,
            weather_base_url=weather_base_url or None,
            irrigation_base_url=irrigation_base_url or None,
            pdm_base_url=pdm_base_url or None,
            pdm_enabled_by_default=pdm_enabled_by_default,
            pdm_default_crop=pdm_default_crop or None,
            pdm_default_model_key=pdm_default_model_key or None,
            resize_max_long_edge=resize_max_long_edge,
            orthophoto_resolution_cm=orthophoto_resolution_cm,
        )
    )
    return RedirectResponse(url='/settings', status_code=303)


@router.post('/ui/settings/credentials')
def update_credentials_ui(
    shared_username: str = Form(''),
    shared_password: str = Form(''),
    openweather_api_key: str = Form(''),
) -> RedirectResponse:
    update_credentials(
        CredentialsUpdateRequest(
            shared_username=shared_username or None,
            shared_password=shared_password or None,
            openweather_api_key=openweather_api_key or None,
        )
    )
    return RedirectResponse(url='/settings', status_code=303)
