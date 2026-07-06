from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from agrivision.app import dependencies as deps
from agrivision.app.formatters import format_duration, format_system_datetime
from agrivision.app.routes import (
    artifacts,
    dashboard,
    diagnostics,
    reports,
    runs,
    services,
    settings,
    uploads,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    deps.settings_service.ensure_runtime_settings_file()
    deps.run_service.reconcile_orphaned_runs()
    yield


app = FastAPI(title='AgriVision Dashboard', version='1.0.0', lifespan=lifespan)
app.mount('/static', StaticFiles(directory=str(Path(__file__).parent / 'web' / 'static')), name='static')

deps.templates.env.filters['system_datetime'] = format_system_datetime
deps.templates.env.filters['duration'] = format_duration

app.include_router(dashboard.router)
app.include_router(diagnostics.router)
app.include_router(runs.router)
app.include_router(uploads.router)
app.include_router(reports.router)
app.include_router(settings.router)
app.include_router(services.router)
app.include_router(artifacts.router)

# Compatibility aliases for tests and scripts that import these from api.py.
storage_service = deps.storage_service
run_service = deps.run_service
report_service = deps.report_service
preflight_service = deps.preflight_service
export_service = deps.export_service
settings_service = deps.settings_service
TEMPLATES = deps.templates
