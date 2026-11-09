# Architecture Overview

AgriVision separates the dashboard, configuration, integrations, processing pipeline, and runtime helpers.

## Entry Points

- Dashboard: operator interface for uploads, runs, reports, settings, and artifacts
- CLI: diagnostics, cleanup, service setup/control, and maintainer workflows

## Main Components

The package is split into layers. Each layer imports only from the layers
above it in this list; `tests/unit/test_layering.py` enforces this.

1. `agrivision/config/`: configuration loading and typed settings (`DEFAULT_CONFIG` holds every default)
2. `agrivision/schemas/`: Pydantic models shared by services and the app, and the safe-ID rule for run/upload folders
3. `agrivision/runtime/`: installing and running the OpenAgri services next to AgriVision (pinned clones, `.env` sync, Docker Compose, health checks, host helper client)
4. `agrivision/integrations/`: HTTP clients and flows for the OpenAgri Weather, Irrigation and Pest & Disease services
5. `agrivision/pipeline/`: orchestration, stages, artifact I/O, grid/risk/report generation
6. `agrivision/services/`: run management, exports, previews, settings persistence and service control
7. `agrivision/app/`: dashboard, API routes, templates and CLI entry

## Data Flow

1. Load configuration and environment overrides.
2. Resolve input, output, and runtime paths.
3. Run or reuse ODM orthophoto generation.
4. Compute vegetation products.
5. Generate grid and risk outputs.
6. Fetch OpenAgri Weather, Irrigation, and Pest & Disease enrichment data.
7. Write artifacts and metadata.
8. Render the final report.

## Outputs

- reports and generated artifacts: `output/`
- per-run saved outputs: `output/runs/<run_id>/`
- run metadata and logs: `runtime/runs/<run_id>/`
- export packages: `runtime/exports/`
- semantic metadata: `metadata/run_metadata.jsonld` inside export packages
