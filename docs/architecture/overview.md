# Architecture Overview

AgriVision keeps the processing logic separate from its transport layers. The two supported entry points are:

- the CLI
- the FastAPI dashboard

## Top-Level Structure

- `agrivision/app/`: HTTP routes, templates, schemas, CLI entry, and presentation concerns
- `agrivision/config/`: config loading, defaults, schema compatibility, typed settings
- `agrivision/domain/`: internal contracts, enums, and core models
- `agrivision/integrations/`: translation between AgriVision and external providers
- `agrivision/pipeline/`: orchestration, stages, artifact I/O, grid/risk/report generation
- `agrivision/runtime/`: environment and Docker/runtime helpers
- `agrivision/services/`: run management, exports, previews, settings persistence, service control

## Execution Model

Normal operator use starts the dashboard through the root Docker Compose stack. The dashboard creates runs, persists run state under `runtime/runs/`, and delegates long-running work to the pipeline/services layer.

The CLI still exists for diagnostics, cleanup, service setup/control, and direct local pipeline execution.

## Data Flow

1. load config and environment overrides
2. resolve input, output, and runtime paths
3. run or reuse ODM orthophoto generation
4. compute vegetation products
5. generate grid and risk outputs
6. fetch OpenAgri enrichment data for enabled report sections
7. write artifacts and metadata
8. render the final report

## Boundary Rules

- `integrations` translates external payloads into internal shapes
- `services` owns concrete provider/runtime behavior
- `pipeline` owns stage sequencing and artifact production
- `app` should not contain pipeline logic

## Related Docs

- deployment details: `docs/architecture/deployment-view.md`
- module boundary notes: `docs/architecture/module-boundaries.md`
- data flow summary: `docs/architecture/data-flow.md`
- interoperability notes: `docs/architecture/interoperability.md`
