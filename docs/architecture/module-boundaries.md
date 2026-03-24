# Module boundaries

This document clarifies the boundaries that are easiest to blur in the repository.

## `integrations` vs `services`

Use `integrations` for translation logic.

Examples:

- adapters that present a pipeline-facing interface;
- mappers that normalize provider-native payloads;
- contract transformations between AgriVision and external systems.

Use `services` for concrete provider behavior.

Examples:

- HTTP clients;
- authentication flows;
- service bootstrap logic;
- provider-specific runtime code.

A useful rule: if the code could change because a vendor endpoint changes, it usually belongs in `services`. If the code exists to protect the rest of AgriVision from vendor-specific shape differences, it usually belongs in `integrations`.

## `runtime` vs `deployment`

Use `runtime` for importable Python code that helps AgriVision understand its execution environment.

Examples:

- Docker path helpers;
- environment sync utilities;
- runtime path resolution.

Use `deployment` for operational artifacts consumed by operators or container engines.

Examples:

- Dockerfiles;
- compose files;
- install scripts;
- shell entrypoints.

A useful rule: if the code is imported by Python modules, it belongs in `runtime`. If it is executed by Docker, Compose, or an operator shell, it belongs in `deployment`.

## Root-level wrappers

Root-level wrappers are preserved to avoid breaking existing commands. New deployment work should target `deployment/` first and then keep wrappers minimal.
