# Open Source Software Documentation

This file is a short release-oriented summary for readers who want one place to understand what this repository ships. It is not a substitute for the operator, developer, API, or architecture docs.

## Identification

- project: AgriVision Pipeline
- repository: `https://github.com/GEvang/agrivision-pipeline`
- version: `1.0.0`
- license: EUPL v1.2
- implementation language: Python

## Scope

AgriVision processes agricultural drone imagery and produces orthophotos, vegetation products, risk outputs, reports, and export packages. It supports both CLI execution and a FastAPI dashboard, with optional integration into OpenAgri companion services.

## Main Capabilities

- dashboard for uploads, run management, reports, settings, and artifacts
- CLI entry points for diagnostics, cleanup, service setup/control, and direct runs
- ODM-backed orthophoto generation
- vegetation, grid, and disease-risk analysis
- optional Weather, Irrigation, and Pest & Disease enrichment
- export packages with `manifest.json` and `metadata/run_metadata.jsonld`

## Deployment Model

The supported operator deployment path is the root Docker Compose stack. Local Python execution remains available for development and advanced usage.

Primary references:

- `README.md`
- `DEPLOYMENT.md`
- `docs/operator/install.md`
- `docs/operator/run.md`
- `docs/developer/local-dev.md`
- `docs/api/README.md`

## Source Structure

- `agrivision/app/`: HTTP and CLI surface
- `agrivision/config/`: configuration loading and typed settings
- `agrivision/domain/`: internal contracts and models
- `agrivision/integrations/`: translation boundaries for external systems
- `agrivision/pipeline/`: stage orchestration and artifact generation
- `agrivision/runtime/`: runtime and container helpers
- `agrivision/services/`: run state, exports, previews, settings persistence, service control

## Inputs and Outputs

Inputs:

- uploaded RGB, MAPIR, and thermal imagery
- imported orthophotos
- non-secret YAML config
- secrets through `.env` or environment variables

Outputs:

- HTML reports
- GeoTIFF rasters and orthophotos
- PNG previews and overlays
- CSV grid and risk artifacts
- JSON and JSON-LD metadata
- ZIP export packages

## Validation

CI validates:

- Python 3.11 and 3.12 environment setup
- linting
- tests with coverage output
- config smoke checks
- Docker Compose config validity
- Docker image buildability

## Known Limits

- public exposure requires external access protection
- ODM workflows are resource-intensive
- companion service enrichments depend on separate service availability and credentials
- ARM or edge hardware support should not be claimed unless a release was actually tested there
