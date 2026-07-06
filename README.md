# AgriVision

AgriVision is a dashboard-first crop risk assessment tool for orthophotos, vegetation analysis, disease-risk scoring, farmer-facing reports, and optional OpenAgri service integrations.

## Quick Start

```bash
git clone https://github.com/GEvang/agrivision-pipeline.git
cd agrivision-pipeline
docker compose up --build -d
```

Open [http://127.0.0.1:8008](http://127.0.0.1:8008).

Base dashboard startup does not require `.env` or the optional OpenAgri services.

## First-Run Expectations

Works immediately:

- dashboard and API
- image uploads
- run tracking
- orthophoto import and reuse flows
- reports and export packages
- runtime folder creation
- default settings in `runtime/settings.json`

Not required before startup:

- `.env`
- Weather, Irrigation, or Pest & Disease companion services
- API keys
- local drone imagery

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
- Troubleshooting: `docs/operator/troubleshooting.md`
- Windows self-hosting: `docs/operator/windows-self-hosting.md`
- Local development: `docs/developer/local-dev.md`
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
