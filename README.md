# AgriVision

AgriVision is a dashboard-first crop risk assessment tool for orthophotos, vegetation analysis, disease-risk scoring, farmer-facing reports, and optional OpenAgri service integrations.

The simplest way to start it is:

```bash
git clone https://github.com/GEvang/agrivision-pipeline.git
cd agrivision-pipeline
docker compose up --build -d
```

Then open [http://127.0.0.1:8008](http://127.0.0.1:8008).

The dashboard starts even if `.env` is missing and even if optional services are not installed yet.

## Quick Start

### Windows

1. Install Docker Desktop.
2. Clone or download AgriVision.
3. Double-click `Start AgriVision Windows.bat`.
4. Your browser opens at [http://127.0.0.1:8008](http://127.0.0.1:8008).

### Linux

1. Install Docker.
2. Clone AgriVision.
3. Run:

```bash
chmod +x "Start AgriVision Linux.sh"
./"Start AgriVision Linux.sh"
```

4. Open [http://127.0.0.1:8008](http://127.0.0.1:8008).

### macOS

1. Install Docker Desktop.
2. Clone or download AgriVision.
3. Run once:

```bash
chmod +x "Start AgriVision macOS.command"
```

4. Double-click `Start AgriVision macOS.command`.
5. Your browser opens at [http://127.0.0.1:8008](http://127.0.0.1:8008).

## What Works On First Launch

- the dashboard and API
- uploads
- run tracking
- orthophoto import/reuse flows
- reports and exported run packages
- runtime folder creation
- default dashboard-managed settings in `runtime/settings.json`

These do not need to exist before the dashboard opens:

- `.env`
- OpenAgri Weather Service
- OpenAgri Irrigation Management
- OpenAgri Pest & Disease Management
- API keys
- drone images
- Docker socket access inside the dashboard container

## Optional Services

The Settings page shows whether optional services are:

- Installed or Not installed
- Connected or Not connected
- Available or Not tested for OpenDroneMap

Missing optional services are shown as dashboard warnings, not startup errors.

## Persistent Folders

The base Docker setup keeps data in these local folders:

- `./data`
- `./output`
- `./runtime`

Important runtime locations:

- uploaded datasets: `data/uploads/<upload_id>/`
- run metadata and logs: `runtime/runs/<run_id>/`
- dashboard settings: `runtime/settings.json`
- saved reports and orthophotos: `output/runs/<run_id>/`
- exported run packages: `runtime/exports/`

## Project Structure

```text
agrivision/
  app/                 FastAPI app, routes, schemas, templates, static assets, CLI
  config/              Config loading, runtime config, typed settings
  domain/              Core contracts and domain models
  integrations/        External service adapters and payload mapping
  pipeline/            Orchestration, stages, grid, risk, report, artifact I/O
  services/            Runs, settings, exports, previews, preflight, service control
config/                Example and environment-specific YAML configs
data/                  Uploaded imagery and local datasets
docs/                  API, architecture, developer, and operator documentation
output/                Generated rasters, reports, run artifacts
runtime/               Run state, logs, previews, exports, settings
tests/                 Unit, integration, and system tests
```

## Advanced / Developer Usage

Python virtualenv setup is still supported for developers and advanced operators, but it is not required just to open the dashboard.

Useful references:

- `docs/operator/install.md`
- `docs/operator/run.md`
- `docs/operator/windows-self-hosting.md`
- `docs/developer/local-dev.md`
- `docs/developer/testing.md`
- `docs/developer/config.md`

## API Docs

When the dashboard is running:

- OpenAPI JSON: [http://127.0.0.1:8008/openapi.json](http://127.0.0.1:8008/openapi.json)
- Swagger UI: [http://127.0.0.1:8008/docs](http://127.0.0.1:8008/docs)
- ReDoc: [http://127.0.0.1:8008/redoc](http://127.0.0.1:8008/redoc)

## OpenAgri Alignment

AgriVision can integrate with OpenAgri Weather, Irrigation, and Pest & Disease services when they are installed and configured, but the dashboard can start independently with safe defaults.

## License

This repository is licensed under the European Union Public Licence (EUPL) v1.2. See `LICENSE`.
