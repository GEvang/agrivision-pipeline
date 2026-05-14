from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

RunStatusValue = Literal['queued', 'running', 'completed', 'failed', 'cancelled']
StageStateValue = Literal['pending', 'running', 'completed', 'failed', 'skipped', 'cancelled']


class StepSelection(BaseModel):
    resize_images: bool = False
    run_odm: bool = True
    fetch_weather: bool = True
    run_irrigation: bool = True
    run_pdm: bool = True
    generate_report: bool = True


class RunParameters(BaseModel):
    preset: str | None = None
    notes: str | None = None
    flight_date: date | None = None
    orthophoto_preset: str | None = None
    orthophoto_resolution_cm: int | None = Field(default=None, ge=1, le=20)
    source_orthophoto_run_id: str | None = None
    pdm_crop: str | None = None
    pdm_model_key: str | None = None


class StageStatus(BaseModel):
    key: str
    label: str
    state: StageStateValue = 'pending'
    message: str | None = None


class RunCreateRequest(BaseModel):
    run_name: str | None = Field(default=None, min_length=1, max_length=120)
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
    started_at: datetime | None = None
    finished_at: datetime | None = None
    dataset_name: str
    input_path: str
    status: RunStatusValue
    progress_percent: int = 0
    current_stage: str = 'queued'
    stage_message: str = 'Queued'
    selected_steps: StepSelection
    parameters: dict[str, Any] = Field(default_factory=dict)
    outputs: dict[str, str] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)
    stages: list[StageStatus] = Field(default_factory=list)
    logs_path: str
    run_name: str | None = None
    field_name: str | None = None


class RunRecord(RunStatus):
    run_dir: str


class RunLaunchResult(BaseModel):
    run_id: str
    status: RunStatusValue
    progress_percent: int = 0
    current_stage: str = 'queued'
    stage_message: str = 'Queued'
    message: str


class UploadManifest(BaseModel):
    run_id: str
    dataset_name: str
    upload_dir: str
    files: list[str]
    mapir_files: list[str] = Field(default_factory=list)
    rgb_files: list[str] = Field(default_factory=list)
    created_at: datetime


class ReportItem(BaseModel):
    run_id: str
    created_at: datetime
    run_name: str | None = None
    dataset_name: str
    status: RunStatusValue
    progress_percent: int = 0
    current_stage: str = 'queued'
    stage_message: str = 'Queued'
    report_path: str | None = None
    orthophoto_path: str | None = None
    preview_path: str | None = None
    quality: dict[str, Any] = Field(default_factory=dict)


class ArtifactLink(BaseModel):
    name: str
    path: str
    exists: bool

    @property
    def filename(self) -> str:
        return Path(self.path).name
