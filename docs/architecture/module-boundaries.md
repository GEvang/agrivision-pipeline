# Module boundaries

This document clarifies the boundaries that are easiest to blur in the repository.

## `integrations` vs `services`

Use `integrations` for translation logic.

Examples:

- adapters that present a pipeline-facing interface;
- mappers that normalize provider-native payloads;
- contract transformations between AgriVision Pipeline and external systems.

Use `services` for concrete provider behavior.

Examples:

- HTTP clients;
- authentication flows;
- service bootstrap logic;
- provider-specific runtime code.

## `runtime` vs operational assets

Use `runtime` for importable Python code that helps AgriVision Pipeline understand its execution environment.

Examples:

- Docker path helpers;
- environment sync utilities;
- runtime path resolution.

Use the repository root operational assets for operator-facing execution.

Examples:

- `Dockerfile`;
- `docker-compose.yml`;
- `docker-entrypoint.sh`.
