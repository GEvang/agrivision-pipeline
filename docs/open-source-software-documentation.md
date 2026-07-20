# Open Source Software Documentation

This file is a short release-oriented summary for readers who want one place to understand what this repository ships. It is not a substitute for the operator, developer, API, or architecture docs.

## Identification

- project: AgriVision Pipeline
- repository: `https://github.com/GEvang/agrivision-pipeline`
- version: `1.0.0`
- license: EUPL v1.2
- implementation language: Python

## Scope

AgriVision processes agricultural drone imagery and produces orthophotos, vegetation products, risk outputs, reports, and export packages. It includes a dashboard, operator commands, and required OpenAgri Weather, Irrigation, and Pest & Disease services for complete field analysis.

## Main Capabilities

- dashboard for uploads, run management, reports, settings, and artifacts
- CLI entry points for diagnostics, cleanup, service setup/control, and direct runs
- ODM-backed orthophoto generation
- vegetation, grid, and disease-risk analysis
- Weather, Irrigation, and Pest & Disease enrichment through required OpenAgri services
- export packages with `manifest.json` and `metadata/run_metadata.jsonld`

## Deployment Model

The supported operator deployment methods are the provided start files and Docker Compose. Maintainer-only code workflows are documented separately and are not operator installation methods.

Primary references:

- `README.md`
- `DEPLOYMENT.md`
- `docs/operator/install.md`
- `docs/operator/run.md`
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

## Operational Notes

- public exposure requires external access protection
- ODM workflows are resource-intensive
- OpenAgri service enrichments require reachable services and credentials
- ARM or edge hardware deployments require release-specific validation
