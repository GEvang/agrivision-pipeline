# AgriVision

AgriVision helps farm teams turn drone imagery into orthophotos, vegetation analysis, disease-risk outputs, reports, and export packages. It is designed to run with the required OpenAgri Weather, Irrigation, and Pest & Disease services.

## Quick Start

Use one of the provided start files:

- Windows: `Start AgriVision Windows.bat`
- Linux: `Start AgriVision Linux.sh`
- macOS: `Start AgriVision macOS.command`

Or start with Docker:

```bash
docker compose up --build -d
```

Open [http://127.0.0.1:8008](http://127.0.0.1:8008).

Before running field analysis, confirm the required OpenAgri Weather, Irrigation, and Pest & Disease services are configured and reachable from the Settings page.

## First-Run Expectations

On first launch, AgriVision creates the local runtime folders used for farm data and reports.

Expected first-run behavior:

- the dashboard opens at `http://127.0.0.1:8008`
- `runtime/settings.json` is created automatically
- the Settings page shows the status of Docker and the required OpenAgri services
- uploaded imagery, reports, exports, and run history are stored in local project folders

## Persistent Data

The default Docker flow persists:

- `data/`
- `output/`
- `runtime/`

Important paths:

- `data/uploads/<upload_id>/`
- `runtime/runs/<run_id>/`
- `runtime/settings.json`
- `runtime/exports/`
- `output/runs/<run_id>/`

## Repository Layout

```text
agrivision/
  app/                 FastAPI app, routes, schemas, templates, static assets, CLI
  config/              Config loading and typed settings
  domain/              Core contracts and models
  integrations/        External service adapters and payload mapping
  pipeline/            Orchestration, stages, grid, risk, report, artifact I/O
  runtime/             Environment and Docker/runtime helpers
  services/            Run, settings, export, preview, and service control logic
config/                Example and environment-specific YAML configs
docs/                  Operator, developer, API, and architecture documentation
tests/                 Unit, integration, and system tests
```

## Read Next

- Operator install: `docs/operator/install.md`
- Daily operation: `docs/operator/run.md`
- Internet deployment: `docs/operator/internet-cloud-deployment.md`
- Troubleshooting: `docs/operator/troubleshooting.md`
- Windows self-hosting: `docs/operator/windows-self-hosting.md`
- Testing: `docs/developer/testing.md`
- Configuration: `docs/developer/config.md`
- API summary: `docs/api/README.md`
- Architecture: `docs/architecture/overview.md`

## API Docs

When the dashboard is running:

- OpenAPI JSON: [http://127.0.0.1:8008/openapi.json](http://127.0.0.1:8008/openapi.json)
- Swagger UI: [http://127.0.0.1:8008/docs](http://127.0.0.1:8008/docs)
- ReDoc: [http://127.0.0.1:8008/redoc](http://127.0.0.1:8008/redoc)

## License

This repository is licensed under the European Union Public Licence (EUPL) v1.2. See `LICENSE`.
