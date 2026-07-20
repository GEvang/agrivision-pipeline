# Architecture Overview

AgriVision separates the dashboard, configuration, integrations, processing pipeline, and runtime helpers.

## Entry Points

- Dashboard: operator interface for uploads, runs, reports, settings, and artifacts
- CLI: diagnostics, cleanup, service setup/control, and maintainer workflows

## Main Components

- `agrivision/app/`: dashboard, API routes, templates, schemas, and CLI entry
- `agrivision/config/`: configuration loading and typed settings
- `agrivision/domain/`: internal contracts and models
- `agrivision/integrations/`: adapters for OpenAgri and other external payloads
- `agrivision/pipeline/`: orchestration, stages, artifact I/O, grid/risk/report generation
- `agrivision/runtime/`: environment and Docker/runtime helpers
- `agrivision/services/`: run management, exports, previews, settings persistence, and service control

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
