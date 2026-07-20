# Open Source Software Documentation

## Identification

- project: AgriVision
- repository: `https://github.com/GEvang/agrivision-pipeline`
- version: `1.0.0`
- license: EUPL v1.2
- implementation language: Python

## Scope

AgriVision processes agricultural drone imagery and produces orthophotos, vegetation products, risk outputs, reports, and export packages. It includes a dashboard, operator commands, and required OpenAgri Weather, Irrigation, and Pest & Disease services for complete field analysis.

## Main Capabilities

- dashboard for uploads, run management, reports, settings, and artifacts
- ODM-backed orthophoto generation
- vegetation, grid, and disease-risk analysis
- Weather, Irrigation, and Pest & Disease enrichment through required OpenAgri services
- export packages with `manifest.json` and `metadata/run_metadata.jsonld`

## Deployment Model

The supported operator deployment methods are the provided start files and Docker Compose. Maintainer-only code workflows are not operator installation methods.

## Source Structure

- `agrivision/app/`: dashboard and API surface
- `agrivision/config/`: configuration loading and typed settings
- `agrivision/domain/`: internal contracts and models
- `agrivision/integrations/`: translation boundaries for external systems
- `agrivision/pipeline/`: stage orchestration and artifact generation
- `agrivision/runtime/`: runtime and container helpers
- `agrivision/services/`: run state, exports, previews, settings persistence, service control

## Validation

CI validates:

- Python 3.11 and 3.12 environment setup
- linting
- tests with coverage output
- config smoke checks
- Docker Compose config validity
- Docker image buildability

## References

- `README.md`
- `DEPLOYMENT.md`
- `docs/api/README.md`
- `docs/architecture/overview.md`
- `docs/developer/testing.md`
