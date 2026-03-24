# AgriVision Pipeline + Dashboard

AgriVision is an OpenAgri-aligned drone imagery pipeline that now supports two operator entry paths without changing the processing core:

- **CLI mode** for scripted or local execution
- **FastAPI + Jinja dashboard** for uploads, run tracking, reports, previews, and settings

The repository remains transport-agnostic at the core. `domain/`, `pipeline/`, `services/`, and `integrations/` still own business logic and integrations. The web layer is a thin adapter under `agrivision/app/`.

## What is new

The dashboard adds:

- image dataset upload
- run checklist / launch form
- filesystem-backed run history
- generated report browsing
- orthophoto preview generation
- safe settings and credential editing

## Hybrid architecture

### Execution core

- `agrivision/domain/` — shared contracts and models
- `agrivision/pipeline/` — orchestration, stages, artifacts, reports
- `agrivision/services/` — runtime helpers, run tracking, previews, settings, reports
- `agrivision/integrations/` — external boundary adapters

### Adapters

- `agrivision/app/cli.py` — CLI entrypoint
- `agrivision/app/api.py` — FastAPI backend and dashboard routes
- `agrivision/app/schemas/` — request / response validation models
- `agrivision/app/web/` — Jinja templates and static assets

### Runtime storage

Dashboard state is filesystem-backed:

- `data/uploads/<upload_id>/` — uploaded image datasets
- `runtime/runs/<run_id>/params.json`
- `runtime/runs/<run_id>/status.json`
- `runtime/runs/<run_id>/outputs.json`
- `runtime/runs/<run_id>/run.log`
- `runtime/runs/<run_id>/previews/`

Each run tracks `run_id`, timestamps, dataset name, selected steps, outputs, errors, and the run log path.

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install -e ".[dev]"
```

Or install from packaging metadata only:

```bash
pip install -e ".[dev]"
```

## CLI usage

### Diagnostics

```bash
python run.py --doctor
```

### Run the pipeline

```bash
python run.py --run-resize
python run.py --skip-odm
python run.py --skip-weather
python run.py --skip-report
```

### Start the dashboard through the CLI

```bash
python run.py --serve-dashboard --host 127.0.0.1 --port 8008
```

## Dashboard usage

You can also start the web UI directly:

```bash
uvicorn agrivision.app.api:app --host 127.0.0.1 --port 8008
```

Pages:

- `/` — dashboard with recent runs and latest outputs
- `/runs/new` — upload images and launch a run
- `/runs/{run_id}` — run detail, logs, artifacts, preview
- `/reports` — report history
- `/settings` — non-secret settings, masked credentials, diagnostics

## Settings and credentials

- non-secret configuration remains in `config.yaml`
- secrets should live in `.env` or environment variables
- the dashboard masks secret values and never returns full secrets in responses
- credentials are written through the service layer and are excluded from logs and run status files

## Operator flow

1. Upload an image dataset on **New Run**
2. Choose the uploaded dataset and processing steps
3. Launch the run
4. Review run status, logs, report links, and orthophoto preview
5. Use **Settings** to update base URLs and credentials safely

## Quality gates

```bash
make lint
make test
make smoke-config
python -m pytest --cov=agrivision --cov-report=term-missing
```

## Documentation map

- `docs/api/README.md` — backend endpoints and dashboard contracts
- `docs/architecture/overview.md` — architecture overview
- `docs/architecture/module-boundaries.md` — execution vs adapter boundaries
- `docs/operator/run.md` — CLI and dashboard operator instructions
- `docs/operator/troubleshooting.md` — operational troubleshooting
