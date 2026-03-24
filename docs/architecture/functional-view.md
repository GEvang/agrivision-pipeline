# Functional view

## Functional subsystems

### Application control

`agrivision.app` exposes a stable CLI for operators and developers. It owns argument parsing, mode selection, and dispatch to operational commands.

### Configuration and domain model

`agrivision.config` loads and validates settings. `agrivision.domain` holds reusable contracts and models shared across pipeline and integration boundaries.

### Pipeline processing

`agrivision.pipeline` owns the processing graph:

- artifact path resolution
- ODM orchestration
- vegetation-index generation
- grid classification
- enrichment stage invocation
- report assembly

### External service translation

`agrivision.integrations` provides thin adapters and mappers that convert concrete service payloads into AgriVision-facing structures.

### Concrete service access

`agrivision.services` contains concrete client code, bootstrap helpers, and long-form interactions with weather and irrigation systems.

### Runtime and deployment support

`agrivision.runtime` and `deployment/` together support execution in local and containerized environments. The former is importable Python support code; the latter is operational packaging material.
