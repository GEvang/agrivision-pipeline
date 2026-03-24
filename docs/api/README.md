# API, contracts, and interoperability guide

AgriVision is not an HTTP API server. Its public contract is a combination of:

- the command-line interface in `agrivision.app.cli`;
- the configuration schema loaded by `agrivision.config.settings`;
- the pipeline artifact layout produced by `agrivision.pipeline`; and
- the service adapter contracts under `agrivision.integrations`.

This document makes those contracts explicit so the repository can be reused as an OpenAgri operating-system component.

## Public entrypoints

### CLI contract

Primary launcher:

```bash
python run.py [--run-resize] [--skip-odm] [--skip-ndvi] [--doctor] [--setup-services] [--cleanup]
```

Behavioral contract:

- `--doctor` prints runtime diagnostics as JSON and exits.
- `--setup-services` prepares sibling OpenAgri services and exits.
- `--cleanup` removes generated outputs and exits.
- default execution runs the pipeline orchestrator.
- `--run-resize`, `--skip-odm`, and `--skip-ndvi` alter stage execution.

### Python package contract

The repository can be installed as a package and the CLI can be invoked through:

```bash
python -m agrivision.app.cli --doctor
```

## Configuration contract

The effective settings model is assembled from:

- YAML configuration under `config.yaml` or `AGRIVISION_CONFIG_PATH`
- environment overrides
- typed settings in `agrivision/config/settings.py`

### High-level config sections

- `paths` — project-relative and output directories
- `pipeline` — feature flags and stage behavior
- `weather` — weather provider credentials and endpoints
- `irrigation` — irrigation service credentials and endpoints
- `runtime` — Docker and host-container path information
- `report` — report generation settings

### Example minimal config shape

```yaml
paths:
  project_root: .
  input_images: data/images_full
  output_root: output
pipeline:
  run_resize: false
  skip_odm: false
  skip_ndvi: false
weather:
  base_url: https://example.invalid/weather
irrigation:
  base_url: https://example.invalid/irrigation
runtime:
  app_container_project_root: /workspace
```

## Artifact contract

The pipeline produces a reproducible artifact family rather than a single opaque blob.

Expected artifact categories include:

- orthophoto outputs from the ODM stage;
- vegetation index rasters and metadata;
- grid classification summaries;
- weather and irrigation enrichment data;
- report assets and rendered HTML output.

Downstream consumers should integrate with named artifact files and metadata written through `agrivision.pipeline.io` instead of scraping logs.

## Integration contracts

### Weather integration boundary

Modules:

- `agrivision.integrations.weather.adapter`
- `agrivision.integrations.weather.mapper`
- `agrivision.services.weather.client`

Contract intent:

- service clients retrieve raw weather data;
- mappers normalize external payloads into AgriVision-friendly structures;
- adapters expose a pipeline-usable boundary.

### Irrigation integration boundary

Modules:

- `agrivision.integrations.irrigation.adapter`
- `agrivision.integrations.irrigation.mapper`
- `agrivision.services.irrigation.*`

Contract intent mirrors the weather boundary: concrete service behavior stays in `services`, while cross-boundary translation stays in `integrations`.

## Semantic interoperability notes

AgriVision should be treated as a producer of field-observation and recommendation-support artifacts. For interoperability work:

- preserve stable field and run identifiers;
- keep timestamps and units explicit;
- document coordinate reference assumptions for geospatial outputs;
- publish enrichment payload mappings rather than provider-native schemas; and
- store metadata next to generated artifacts whenever stage outputs are consumed by other OpenAgri services.

## Stability and versioning

Versioning is currently repository-based. Until a separate API versioning scheme exists, consumers should pin to tagged releases or commit hashes and validate:

- CLI flag compatibility
- configuration keys
- output artifact locations
- metadata file structure

## Recommended consumer patterns

Preferred integration approaches, in order:

1. call the CLI with a version-pinned installation;
2. exchange data through documented config and artifact contracts;
3. use `agrivision.pipeline.orchestrator` only from trusted internal code;
4. avoid depending on deployment scripts as a programmatic API.
