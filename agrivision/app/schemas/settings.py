from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


class SettingsUpdateRequest(BaseModel):
    location_name: str | None = Field(default=None, max_length=200)
    location_lat: float | None = Field(default=None, ge=-90, le=90)
    location_lon: float | None = Field(default=None, ge=-180, le=180)
    weather_base_url: str | None = Field(default=None, max_length=500)
    irrigation_base_url: str | None = Field(default=None, max_length=500)
    pdm_base_url: str | None = Field(default=None, max_length=500)
    pdm_enabled_by_default: bool | None = None
    pdm_default_crop: str | None = Field(default=None, max_length=120)
    pdm_default_model_key: str | None = Field(default=None, max_length=120)
    resize_max_long_edge: int | None = Field(default=None, ge=256, le=12000)
    orthophoto_resolution_cm: int | None = Field(default=None, ge=1, le=50)
    deployment_mode: str | None = Field(default=None, max_length=40)
    public_url: str | None = Field(default=None, max_length=500)
    min_free_disk_gb: int | None = Field(default=None, ge=0, le=10000)
    max_active_odm_runs: int | None = Field(default=None, ge=1, le=10)
    external_access_protection_confirmed: bool | None = None

    @field_validator(
        'location_name',
        'weather_base_url',
        'irrigation_base_url',
        'pdm_base_url',
        'pdm_default_crop',
        'pdm_default_model_key',
        'deployment_mode',
        'public_url',
    )
    @classmethod
    def _clean_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator('deployment_mode')
    @classmethod
    def _validate_deployment_mode(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if value not in {'local', 'self_hosted', 'cloud'}:
            raise ValueError('deployment_mode must be local, self_hosted, or cloud')
        return value


class CredentialsUpdateRequest(BaseModel):
    shared_username: str | None = None
    shared_password: str | None = None
    openweather_api_key: str | None = None
    irrigation_token: str | None = None
    pdm_token: str | None = None
    weather_username: str | None = None
    weather_password: str | None = None
    irrigation_email: str | None = None
    irrigation_password: str | None = None
    pdm_username: str | None = None
    pdm_password: str | None = None


class SettingsView(BaseModel):
    non_secret: dict[str, Any]
    credentials: dict[str, str]
    diagnostics: dict[str, Any]
