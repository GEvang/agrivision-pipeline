from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

RunStatusValue = Literal['queued', 'running', 'completed', 'failed']


class StepSelection(BaseModel):
    resize_images: bool = False
    run_odm: bool = True
    generate_orthophoto: bool = True
    fetch_weather: bool = True
    generate_report: bool = True


class RunParameters(BaseModel):
    preset: str | None = None
    notes: str | None = None
    flight_date: date | None = None


class RunCreateRequest(BaseModel):
    run_name: str = Field(min_length=1, max_length=120)
    dataset_name: str = Field(min_length=1, max_length=120)
    field_name: str | None = Field(default=None, max_length=120)
    selected_steps: StepSelection = Field(default_factory=StepSelection)
    parameters: RunParameters = Field(default_factory=RunParameters)
    upload_run_id: str = Field(min_length=1)

    @field_validator('run_name', 'dataset_name', 'field_name')
    @classmethod
    def _strip_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError('Value must not be blank.')
        return stripped


class RunStatus(BaseModel):
    run_id: str
    created_at: datetime
    updated_at: datetime | None = None
    dataset_name: str
    input_path: str
    status: RunStatusValue
    selected_steps: StepSelection
    parameters: dict[str, Any] = Field(default_factory=dict)
    outputs: dict[str, str] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)
    logs_path: str
    run_name: str | None = None
    field_name: str | None = None


class RunRecord(RunStatus):
    run_dir: str


class RunLaunchResult(BaseModel):
    run_id: str
    status: RunStatusValue
    message: str


class UploadManifest(BaseModel):
    run_id: str
    dataset_name: str
    upload_dir: str
    files: list[str]
    created_at: datetime


class ReportItem(BaseModel):
    run_id: str
    created_at: datetime
    dataset_name: str
    status: RunStatusValue
    report_path: str | None = None
    orthophoto_path: str | None = None
    preview_path: str | None = None


class ArtifactLink(BaseModel):
    name: str
    path: str
    exists: bool

    @property
    def filename(self) -> str:
        return Path(self.path).name
