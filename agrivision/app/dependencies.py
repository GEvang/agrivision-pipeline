from __future__ import annotations

from pathlib import Path

from fastapi.templating import Jinja2Templates

from agrivision.config.settings import load_local_env
from agrivision.services.export_service import RunExportService
from agrivision.services.preflight_service import PreflightService
from agrivision.services.report_service import ReportService
from agrivision.services.run_service import RunService
from agrivision.services.settings_service import SettingsService
from agrivision.services.storage_service import StorageService

load_local_env()

storage_service = StorageService()
run_service = RunService(storage_service)
report_service = ReportService(run_service=run_service)
preflight_service = PreflightService(storage_service)
export_service = RunExportService(run_service=run_service, storage=storage_service)
settings_service = SettingsService()
templates = Jinja2Templates(directory=str(Path(__file__).parent / 'web' / 'templates'))

ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.tif', '.tiff'}
MINIMUM_DATASET_IMAGES = 2
