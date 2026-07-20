# AgriVision API And Dashboard Contract

The dashboard is a thin FastAPI adapter over the pipeline core. Route handlers delegate to service-layer modules so HTTP concerns stay out of `pipeline/`, `integrations/`, and `domain/`.

## Core Endpoints

FastAPI publishes machine-readable and human-readable API documentation:

- `GET /openapi.json`
- `GET /docs` for Swagger UI
- `GET /redoc` for ReDoc

### Health

- `GET /health`
- `GET /doctor`

### Uploads

- `POST /uploads/images`
  - multipart form
  - validates file types, duplicate names, empty files, and unreadable images
  - stores datasets under `data/uploads/<upload_id>/`

### Runs

- `GET /runs`
- `GET /runs/{run_id}`
- `POST /runs`
- `POST /runs/validate`
- `GET /runs/{run_id}/status`
- `POST /runs/{run_id}/stop`
- `GET /runs/{run_id}/package`

### Reports

- `GET /reports`
- `GET /reports/{run_id}`
- `GET /reports/{run_id}/view`

### Settings And Services

- `GET /settings`
- `POST /settings`
- `POST /settings/credentials`
- `GET /services/status`

### Browser Form Routes

The dashboard also exposes `/ui/...` routes for browser form posts and workflow actions. These are not a stable public API contract for external clients. If you are integrating programmatically, prefer the documented JSON endpoints and the generated OpenAPI spec.

### Artifacts

- `GET /artifacts/{run_id}/report`
- `GET /artifacts/{run_id}/orthophoto`
- `GET /artifacts/{run_id}/orthophoto-rgb`
- `GET /artifacts/{run_id}/orthophoto-mapir`
- `GET /artifacts/{run_id}/orthophoto-thermal`
- `GET /artifacts/{run_id}/preview`
- `GET /artifacts/{run_id}/log`
- `GET /artifacts/{run_id}/report-assets/{asset_path}`

Run packages include:

- `manifest.json` for simple file inventory
- `metadata/run_metadata.jsonld` for OpenAgri-oriented semantic interchange
- run status, parameters, logs, reports, rasters, and quality artifacts when present

## Dashboard Pages

- `/` dashboard
- `/runs/new` new run form
- `/runs/{run_id}` run detail
- `/ui/orthophotos` orthophoto creation and import workflows
- `/reports` report history
- `/settings` settings and credentials

## Run Persistence

Each run is stored under `runtime/runs/<run_id>/`.

- `params.json`: selected steps and submitted parameters
- `status.json`: current status, timestamps, outputs, errors
- `outputs.json`: discovered report / orthophoto paths
- `run.log`: captured pipeline log
- `previews/`: derived orthophoto preview images

## Security Model

Non-secret settings are editable through `config.yaml`. Secrets are written to `.env` and masked in UI responses. Full credential values are never returned to the browser.
