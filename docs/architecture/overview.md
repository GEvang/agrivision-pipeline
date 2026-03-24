# Architecture overview

AgriVision is organized as a layered processing service with explicit repository boundaries.

## Top-level architecture

1. `agrivision.app` — command-line and operational entrypoints.
2. `agrivision.config` — configuration loading, validation, and typed settings.
3. `agrivision.domain` — shared models and contracts.
4. `agrivision.pipeline` — stage orchestration, artifact I/O, and report generation.
5. `agrivision.integrations` — thin external-boundary adapters and mappers.
6. `agrivision.services` — concrete weather and irrigation service clients plus service runtime helpers.
7. `agrivision.runtime` — environment, Docker, and bootstrap utilities.
8. `deployment/` — canonical scripts and container assets.

## Design intent

The codebase is structured to preserve a clean separation between:

- application control flow;
- domain and configuration concerns;
- core pipeline logic;
- external-system translation;
- concrete service implementations; and
- deployment/runtime mechanics.

This prevents the common failure mode where one script layer begins to own business logic, environment setup, and third-party integrations all at once.

## Canonical execution path

A normal invocation flows through these boundaries:

`run.py` → `agrivision.app.cli` → command handler → `agrivision.pipeline.orchestrator` → stage modules → I/O and report generation → optional enrichments.

## Canonical deployment path

Use `deployment/docker/` as the source of truth for container assets. Root-level Docker and shell entrypoints remain convenience wrappers so existing operator commands do not break.

## Related views

- `functional-view.md` describes responsibilities by subsystem.
- `information-view.md` describes the main data objects and exchange points.
- `data-flow.md` describes stage sequencing.
- `deployment-view.md` describes runtime packaging.
- `module-boundaries.md` clarifies the distinction between `integrations`, `services`, `runtime`, and `deployment`.
