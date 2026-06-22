# AgriVision Pipeline

AgriVision Pipeline is a Python/FastAPI drone-imagery processing application for OpenAgri-aligned agricultural workflows. It can run as a CLI pipeline or as an operator dashboard over the same processing core.

The pipeline processes RGB, MAPIR/multispectral, and thermal imagery where available; creates or reuses OpenDroneMap orthophotos; computes vegetation-index and grid products; enriches runs with OpenAgri Weather, Irrigation, and Pest & Disease data when configured; and writes farmer-ready HTML reports plus export packages.

## Key Features

- CLI entrypoint through `python run.py` or the installed `agrivision` console script.
- FastAPI dashboard for uploads, run tracking, orthophoto workflows, reports, settings, service control, and artifact downloads.
- OpenDroneMap integration through Docker for RGB, MAPIR, and thermal orthophoto generation.
- Vegetation-index raster generation, grid classification, disease-risk scoring, and HTML reporting.
- Optional OpenAgri service enrichment for Weather, Irrigation Management, and Pest & Disease Management.
- Runtime persistence under `runtime/runs/` and generated outputs under `output/`.
- Docker Compose deployment surface for local/self-hosted dashboard operation.

## Requirements

- Python 3.11 or 3.12. The package metadata requires `>=3.11`; CI validates both 3.11 and 3.12.
- `pip`, `venv`, and a working C/C++/geospatial dependency environment for `rasterio`.
- GDAL command-line tools such as `gdalinfo` for raster/orthophoto workflows.
- Docker with Compose support for ODM stages and the containerized dashboard flow.
- Git when using the installer or service bootstrap helpers.

The root `Dockerfile` uses `python:3.12-slim` and installs GDAL, Git, Docker CLI, and Docker Compose plugin inside the image.

## Installation

Canonical Linux/macOS operator setup:

```bash
git clone https://github.com/GEvang/agrivision-pipeline.git
cd agrivision-pipeline
chmod +x install_agrivision.sh
./install_agrivision.sh
source .venv/bin/activate
python run.py --doctor
```

Manual development setup:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -e ".[dev]"
cp .env.example .env
python run.py --doctor
```

On Windows PowerShell, create/activate the virtual environment with:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
python run.py --doctor
```

## Configuration

AgriVision loads defaults from `agrivision/config/settings.py`, merges non-secret values from `config.yaml`, then applies `.env` or process environment overrides.

- Keep non-secret settings in `config.yaml`.
- Keep credentials and tokens in `.env` or exported environment variables.
- Use `config/config.example.yaml`, `config/config.dev.yaml`, or `config/config.edge.yaml` as references for local variants.
- Override the active config file with `AGRIVISION_CONFIG_PATH=/path/to/config.yaml`.
- In containers, `APP_CONTAINER_PROJECT_ROOT` enables loopback service URL rewriting from `127.0.0.1`/`localhost` to `host.docker.internal` unless `AGRIVISION_REWRITE_LOOPBACK_URLS=0`.

Supported secret/environment overrides from `.env.example`:

```env
WEATHER_USERNAME=
WEATHER_PASSWORD=
OPENWEATHER_API_KEY=
IRRIGATION_EMAIL=
IRRIGATION_PASSWORD=
IRRIGATION_TOKEN=
PDM_USERNAME=
PDM_PASSWORD=
PDM_TOKEN=
AGRIVISION_DEPLOYMENT_MODE=local
AGRIVISION_PUBLIC_URL=
AGRIVISION_MIN_FREE_DISK_GB=50
AGRIVISION_MAX_ACTIVE_ODM_RUNS=1
AGRIVISION_EXTERNAL_ACCESS_PROTECTION_CONFIRMED=false
```

The dashboard masks secrets and does not return full credential values in responses.

## Local Usage

Diagnostics:

```bash
python run.py --doctor
```

Run the CLI pipeline:

```bash
python run.py
```

Start the dashboard:

```bash
python run.py --serve-dashboard --host 127.0.0.1 --port 8008
```

Open `http://127.0.0.1:8008`.

FastAPI documentation is available from the running dashboard:

- OpenAPI JSON: `http://127.0.0.1:8008/openapi.json`
- Swagger UI: `http://127.0.0.1:8008/docs`
- ReDoc: `http://127.0.0.1:8008/redoc`

Useful CLI flags:

```bash
python run.py --skip-odm
python run.py --skip-ndvi
python run.py --skip-weather
python run.py --skip-report
python run.py --setup-services
python run.py --cleanup
```

## Build, Test, and Lint

Common commands are defined in the `Makefile`:

```bash
make install-dev
make lint
make test
make smoke-config
make verify-phase5
make serve-dashboard
```

Equivalent direct commands:

```bash
python -m ruff check .
python -m pytest tests
python -m pytest tests --cov=agrivision --cov-report=term-missing
python -c "from agrivision.config.settings import load_config; load_config(); print('config smoke check passed')"
```

CI runs linting, tests with coverage, config loading, Docker Compose validation, and Dockerfile build validation on Python 3.11 and 3.12.

## Docker

Root-level Docker assets are the supported container deployment surface:

```bash
docker compose config
docker compose build
docker compose up
```

The Compose service publishes the dashboard on port `8008`, mounts the repository at `/workspace`, mounts `/var/run/docker.sock`, and starts:

```bash
python run.py --serve-dashboard --host 0.0.0.0 --port 8008
```

ODM stages require Docker socket access so the application can launch OpenDroneMap containers. If `/var/run/docker.sock` is not mounted, the dashboard can start but ODM stages will fail.

For a Windows workstation exposed through Cloudflare Tunnel, see `docs/operator/windows-self-hosting.md`.

## Project Structure

```text
agrivision/
  app/                 FastAPI app, routes, schemas, CLI, templates, static assets
  config/              Config loading, runtime config, typed settings
  domain/              Core contracts, enums, and domain models
  integrations/        Provider adapters and payload mapping
  pipeline/            Orchestration, stages, grid, risk, report, and artifact I/O
  runtime/             Docker/runtime/bootstrap helpers
  services/            Runtime services for runs, reports, settings, previews, exports, and provider control
config/                Example/dev/edge YAML configs
data/                  Local input imagery, uploads, ODM project folders
docs/                  API, architecture, developer, and operator documentation
output/                Generated rasters, reports, run artifacts, enrichment outputs
runtime/runs/          Dashboard run records, logs, status, previews, packages
tests/                 Unit, integration, and system tests
```

## Runtime Storage

- `data/uploads/<upload_id>/`: uploaded image datasets and manifests.
- `runtime/runs/<run_id>/params.json`: submitted run parameters.
- `runtime/runs/<run_id>/status.json`: current run status, timestamps, errors, and progress.
- `runtime/runs/<run_id>/outputs.json`: discovered report, orthophoto, preview, and related artifact paths.
- `runtime/runs/<run_id>/run.log`: captured pipeline log.
- `runtime/runs/<run_id>/previews/`: derived preview images.
- `output/`: generated NDVI products, grids, reports, weather/irrigation/PDM outputs, and run artifacts.

## Troubleshooting

- If `python run.py --doctor` fails, confirm the virtual environment is active and dependencies were installed with `python -m pip install -e ".[dev]"`.
- If raster or ODM steps fail early, confirm GDAL tools are installed and Docker is running.
- If ODM fails inside Docker Compose, confirm `/var/run/docker.sock` is mounted and accessible.
- If Weather, Irrigation, or PDM enrichment fails, verify service URLs in `config.yaml` and credentials in `.env`. Enrichment failures are designed to degrade reports rather than stop the whole pipeline where possible.
- If the dashboard is exposed publicly, set `AGRIVISION_DEPLOYMENT_MODE`, `AGRIVISION_PUBLIC_URL`, and `AGRIVISION_EXTERNAL_ACCESS_PROTECTION_CONFIRMED` only after external access protection is configured.

## Documentation

- `docs/api/README.md`: dashboard and API contract.
- `docs/operator/install.md`: operator installation.
- `docs/operator/run.md`: operator run commands and outputs.
- `docs/operator/windows-self-hosting.md`: Windows Docker Desktop and Cloudflare Tunnel setup.
- `docs/operator/offline-edge.md`: constrained/offline operating notes.
- `docs/developer/local-dev.md`: editable install and raw FastAPI development server.
- `docs/developer/testing.md`: test and CI commands.
- `docs/developer/config.md`: configuration and secret handling.
- `docs/architecture/`: module boundaries, data flow, deployment view, and interoperability notes.

## License and Contributions

This repository is licensed under the European Union Public Licence (EUPL) v1.2; see `LICENSE`.

No dedicated contribution guide is currently present. For changes, follow the existing style, keep secrets out of config and commits, run `make lint` and `make test`, and update documentation when behavior or commands change. See `docs/developer/release.md` for release and license review notes.
