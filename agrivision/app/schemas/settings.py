from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


class SettingsUpdateRequest(BaseModel):
    location_name: str | None = Field(default=None, max_length=200)
    weather_base_url: str | None = Field(default=None, max_length=500)
    irrigation_base_url: str | None = Field(default=None, max_length=500)
    resize_max_long_edge: int | None = Field(default=None, ge=256, le=12000)
    orthophoto_resolution_cm: int | None = Field(default=None, ge=1, le=50)

    @field_validator('location_name', 'weather_base_url', 'irrigation_base_url')
    @classmethod
    def _clean_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class CredentialsUpdateRequest(BaseModel):
    weather_username: str | None = None
    weather_password: str | None = None
    openweather_api_key: str | None = None
    irrigation_email: str | None = None
    irrigation_password: str | None = None
    irrigation_token: str | None = None


class SettingsView(BaseModel):
    non_secret: dict[str, Any]
    credentials: dict[str, str]
    diagnostics: dict[str, Any]
