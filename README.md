# AgriVision Pipeline

AgriVision is an OpenAgri-aligned drone imagery pipeline for orthophoto generation, vegetation index computation, grid-based field classification, external service enrichment, and farmer-facing HTML reporting.

The repository is structured as a reusable operating-system service component rather than a single script bundle. It separates application entrypoints, configuration, domain contracts, pipeline stages, integrations, runtime helpers, and deployment assets so contributors can reason about the system boundary-by-boundary.

## What the pipeline does

Given a project folder with input imagery and configuration, AgriVision can:

1. prepare input imagery for processing;
2. run or reuse ODM orthophoto generation;
3. compute vegetation-index artifacts;
4. classify the field into grid cells;
5. enrich outputs from weather and irrigation services; and
6. render an HTML report suitable for operator review.

## Repository map

### Runtime and application layer

- `run.py` — stable user-facing launcher kept for backwards compatibility.
- `agrivision/app/` — CLI parser, operational commands, and command dispatch.
- `agrivision/runtime/` — environment, Docker, and bootstrap helpers for execution contexts.
- `deployment/` — canonical deployment assets, container entrypoints, and install scripts.

### Core processing layer

- `agrivision/pipeline/` — orchestrator, state model, stages, artifact I/O, and report rendering.
- `agrivision/domain/` — typed contracts and shared models used across layers.
- `agrivision/config/` — config loading, schema splitting, and validated settings.

### External boundary layer

- `agrivision/integrations/` — thin adapters and mappers that translate between AgriVision contracts and external systems.
- `agrivision/services/` — concrete service clients and runtime support code for long-form external interactions.

### Supporting assets

- `docs/` — architecture, API/contracts, operator, and developer documentation.
- `tests/` — unit, integration, and system tests.
- `.github/workflows/` — CI automation.
- `requirements.txt` — pinned runtime dependency set for reproducible installs.

## Architectural boundary rules

The most important repository boundaries are:

- `app` owns command-line interaction and user-triggered workflows.
- `pipeline` owns stage orchestration and artifact production.
- `integrations` owns translation at system boundaries.
- `services` owns concrete external client behavior and service bootstrapping.
- `runtime` owns execution-environment concerns such as Docker paths, bootstrap helpers, and environment sync.
- `deployment` owns install-time and container-time assets only.

This split prevents application code from accumulating deployment logic and keeps external-service coupling out of the core pipeline.

## Installation

### Local Python install

```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[dev]"
```

For locked runtime installs, use:

```bash
pip install -r requirements.txt
pip install -e ".[dev]"
```

## Quick start

### Validate the environment

```bash
python run.py --doctor
```

### Run the pipeline

```bash
python run.py --run-resize
```

### Useful flags

```bash
python run.py --skip-odm
python run.py --skip-ndvi
python run.py --cleanup
python run.py --setup-services
```

## Configuration model

- Root config file: `config.yaml`
- Example config: `config/config.example.yaml`
- Edge profile: `config/config.edge.yaml`
- Developer profile: `config/config.dev.yaml`
- Environment override entrypoint: `.env`

Secrets should be injected through environment variables where possible rather than committed into YAML. The settings loader already warns when secret material is read directly from configuration files.

## Deployment paths

The canonical container assets live under `deployment/docker/`.

The root-level `Dockerfile`, `docker-compose.yml`, `bootstrap.sh`, and `install_agrivision.sh` are compatibility wrappers kept for convenience and operator ergonomics. They point to the same deployment model and should not be treated as a second independent deployment stack.

## Documentation guide

- Architecture overview: `docs/architecture/overview.md`
- Functional boundaries: `docs/architecture/functional-view.md`
- Information and interoperability view: `docs/architecture/information-view.md`
- Data flow: `docs/architecture/data-flow.md`
- Deployment view: `docs/architecture/deployment-view.md`
- Module boundary clarification: `docs/architecture/module-boundaries.md`
- API and contract guide: `docs/api/README.md`
- Operator install/run docs: `docs/operator/`
- Developer workflow docs: `docs/developer/`

## Quality gates

```bash
make lint
make test
make smoke-config
python -m pytest --cov=agrivision --cov-report=term-missing
```

## OpenAgri alignment highlights

This repository has been organized to support OpenAgri-oriented reuse by:

- documenting clear architectural views;
- surfacing data contracts and integration boundaries;
- separating core orchestration from deployment mechanics;
- keeping reproducible pinned dependencies; and
- providing local, CI, and container execution paths.
