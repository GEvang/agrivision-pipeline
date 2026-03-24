# Architecture overview

AgriVision Pipeline is organized as a layered processing service with explicit repository boundaries.

## Top-level architecture

1. `agrivision.app` — command-line and dashboard entrypoints.
2. `agrivision.config` — configuration loading, validation, and typed settings.
3. `agrivision.domain` — shared models and contracts.
4. `agrivision.pipeline` — stage orchestration, artifact I/O, and report generation.
5. `agrivision.integrations` — thin external-boundary adapters and mappers.
6. `agrivision.services` — concrete weather and irrigation clients plus runtime helpers.
7. `agrivision.runtime` — environment and Docker helpers.
8. `deployment/` — supplementary deployment examples and internal helper material.

## Design intent

The codebase preserves a separation between:

- application control flow;
- domain and configuration concerns;
- core pipeline logic;
- external-system translation; and
- deployment/runtime mechanics.

## Canonical execution path

A normal invocation flows through these boundaries:

`run.py` → `agrivision.app.cli` → command handler → `agrivision.pipeline.orchestrator` → stage modules → I/O and report generation → optional enrichments.

## Canonical deployment path

Use the root-level install and runtime assets for operator flows. Raw framework commands and lower-level container commands remain developer-oriented.
