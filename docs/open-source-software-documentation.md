# Open Source Software Documentation Template

## 1. Software Identification

Software Title: AgriVision Pipeline

Short Description: Python/FastAPI drone-imagery processing application for OpenAgri-aligned agricultural workflows. It provides a CLI and operator dashboard for orthophoto creation/reuse, vegetation-index processing, grid assessment, OpenAgri service enrichment, and HTML/report package generation.

Keywords/Tags: digital agriculture, drone imagery, orthophoto, OpenDroneMap, vegetation index, NDVI, FastAPI, OpenAgri, irrigation, weather, pest and disease, dashboard, CLI

Author(s)/Maintainer(s): Nektarios Fakidaris, Giannis Evangelou

Organization: Aigaio Skytech, working on AgriVision Pipeline for the OpenAgri project.

Contact Email: Primary: `nekfakidaris@gmail.com`; secondary/software engineering contact: `gevang97@outlook.com`

Repository URL: `https://github.com/GEvang/agrivision-pipeline`

Docker image/registry URL: No published Docker registry URL. Docker images are built locally; the local Compose image name is `agrivision-pipeline:phase5`.

Version: `1.0.0`

Release Date: 2026-05-28

Programming Language(s): Python

Operating System(s): Linux/macOS local operator flow; Windows PowerShell local development flow; Windows Docker Desktop self-hosting flow; Docker container based on `python:3.12-slim`. CI validates Ubuntu with Python 3.11 and 3.12.

Primary source references: `README.md`, `pyproject.toml`, `requirements.txt`, `Makefile`, `Dockerfile`, `docker-compose.yml`, `.github/workflows/ci.yml`, `docs/`.

## 2. Purpose and Scope

AgriVision Pipeline processes agricultural drone imagery for operator-facing analysis and reporting. The software processes RGB, MAPIR/multispectral, and thermal imagery where available; creates or reuses OpenDroneMap orthophotos; computes vegetation-index and grid products; enriches runs with OpenAgri Weather, Irrigation Management, and Pest & Disease services when configured; and writes farmer-ready HTML reports plus export packages.

Intended users include project operators, agronomists, field teams, and developers integrating drone-derived artifacts into OpenAgri-style systems.

## 3. Features and Functionality

- CLI entrypoint through `python run.py` and package console script `agrivision`.
- FastAPI dashboard for uploads, run tracking, orthophoto workflows, reports, settings, service control, and artifact downloads.
- OpenDroneMap integration through Docker for RGB, MAPIR, and thermal orthophoto generation.
- Vegetation-index raster generation and grid classification.
- Disease-risk scoring layers.
- Optional enrichment from OpenAgri Weather, Irrigation Management, and Pest & Disease services.
- HTML report rendering and report asset management.
- Run persistence under `runtime/runs/`.
- Export packages containing run status, parameters, logs, reports, rasters, quality artifacts, `manifest.json`, and `metadata/run_metadata.jsonld`.
- Docker Compose deployment surface for local/self-hosted dashboard operation.

## 4. System Architecture

AgriVision Pipeline keeps a transport-agnostic processing core and two supported adapters: the CLI and the dashboard.

Main modules:

- `agrivision/app/`: FastAPI application, CLI, routes, schemas, templates, static assets, and dashboard formatting.
- `agrivision/config/`: YAML/environment config loading, runtime config, schema compatibility, and typed settings.
- `agrivision/domain/`: core contracts, enums, and domain models.
- `agrivision/integrations/`: external provider adapters and payload mapping.
- `agrivision/pipeline/`: orchestration, processing stages, grid/risk/report code, and artifact I/O.
- `agrivision/runtime/`: Docker/runtime/bootstrap helpers.
- `agrivision/services/`: run, report, settings, preview, export, diagnostics, provider bootstrap, and service-control logic.

Data flow:

1. load configuration and environment overrides;
2. resolve project, input, and output paths;
3. run or reuse ODM orthophoto generation;
4. compute vegetation-index products;
5. generate grid classifications and summaries;
6. fetch or map weather and irrigation enrichment data;
7. write metadata and report assets;
8. render the HTML report.

## 5. Installation and Setup

System requirements:

- Python 3.11 or 3.12; package metadata requires `>=3.11`, and CI validates both 3.11 and 3.12.
- `pip`, `venv`, and geospatial support needed by `rasterio`.
- GDAL command-line tools such as `gdalinfo` for raster/orthophoto workflows.
- Docker with Compose support for ODM stages and containerized dashboard operation.
- Git when using the installer or service bootstrap helpers.

Dependencies:

- Runtime Python dependencies are defined in `pyproject.toml` and pinned in `requirements.txt`.
- Main runtime dependencies: `fastapi`, `uvicorn`, `jinja2`, `python-multipart`, `pydantic`, `rasterio`, `numpy`, `matplotlib`, `pillow`, `PyYAML`, `requests`, `click`, `affine`, `attrs`, `packaging`.
- Development dependencies: `pytest`, `pytest-cov`, `httpx`, `ruff`, `black`.
- External tool/container dependency: OpenDroneMap Docker image configured by `orthophoto.odm_docker_image`.

Canonical Linux/macOS operator installation:

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

Windows PowerShell setup:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
python run.py --doctor
```

Configuration:

- Defaults are loaded from `agrivision/config/settings.py`.
- Non-secret overrides are loaded from `config.yaml` or an `AGRIVISION_CONFIG_PATH` override.
- Secrets and deployment settings are loaded from `.env` or exported environment variables.
- Secret-like YAML values are cleared during load and must be supplied through `.env` or the process environment.

Supported environment variables from `.env.example`:

- `WEATHER_USERNAME`
- `WEATHER_PASSWORD`
- `OPENWEATHER_API_KEY`
- `IRRIGATION_EMAIL`
- `IRRIGATION_PASSWORD`
- `IRRIGATION_TOKEN`
- `PDM_USERNAME`
- `PDM_PASSWORD`
- `PDM_TOKEN`
- `AGRIVISION_DEPLOYMENT_MODE`
- `AGRIVISION_PUBLIC_URL`
- `AGRIVISION_MIN_FREE_DISK_GB`
- `AGRIVISION_MAX_ACTIVE_ODM_RUNS`
- `AGRIVISION_EXTERNAL_ACCESS_PROTECTION_CONFIRMED`

## 6. Usage Instructions

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

Common CLI flags:

```bash
python run.py --skip-odm
python run.py --skip-ndvi
python run.py --skip-weather
python run.py --skip-report
python run.py --setup-services
python run.py --cleanup
```

Docker Compose flow:

```bash
docker compose config
docker compose build
docker compose up
```

The Compose service starts:

```bash
python run.py --serve-dashboard --host 0.0.0.0 --port 8008
```

User interface description:

The dashboard provides pages for the run dashboard (`/`), new run form (`/runs/new`), run details (`/runs/{run_id}`), report history (`/reports`), and settings/credentials (`/settings`).

## 7. Input/Output Specifications

Input formats:

- Uploaded image datasets via multipart upload, grouped as RGB, MAPIR, and/or thermal images.
- Ready orthophoto imports through dashboard orthophoto workflows.
- YAML configuration in `config.yaml` or equivalent `AGRIVISION_CONFIG_PATH`.
- Environment variables and `.env` credentials.
- Run creation JSON matching `RunCreateRequest` in `agrivision/app/schemas/runs.py`.

Output formats:

- HTML reports.
- GeoTIFF rasters and orthophotos.
- PNG report/quality preview assets.
- CSV grid and disease-risk cell outputs.
- JSON metadata, status, settings, weather, irrigation, PDM, and quality outputs.
- JSON-LD run metadata in export packages.
- ZIP export packages under runtime exports.
- Plain-text run logs.

Data validation:

- `RunCreateRequest` validates dataset names, run names, field names, selected steps, parameters, and upload run IDs.
- Upload routes validate file type, duplicate names, empty files, and unreadable/corrupt images.
- Settings routes validate coordinate ranges, URL/text lengths, deployment mode values, disk/concurrency limits, and orthophoto resolution bounds.

## 8. API Documentation (If Applicable)

FastAPI publishes generated documentation from the running dashboard:

- OpenAPI JSON: `http://127.0.0.1:8008/openapi.json`
- Swagger UI: `http://127.0.0.1:8008/docs`
- ReDoc: `http://127.0.0.1:8008/redoc`

Documented core endpoints:

- `GET /health`
- `GET /doctor`
- `POST /uploads/images`
- `GET /runs`
- `GET /runs/{run_id}`
- `POST /runs`
- `POST /runs/validate`
- `GET /runs/{run_id}/status`
- `POST /runs/{run_id}/stop`
- `GET /runs/{run_id}/package`
- `GET /reports`
- `GET /reports/{run_id}`
- `GET /reports/{run_id}/view`
- `GET /settings`
- `POST /settings`
- `POST /settings/credentials`
- `GET /services/status`
- `GET /artifacts/{run_id}/report`
- `GET /artifacts/{run_id}/orthophoto`
- `GET /artifacts/{run_id}/orthophoto-rgb`
- `GET /artifacts/{run_id}/orthophoto-mapir`
- `GET /artifacts/{run_id}/orthophoto-thermal`
- `GET /artifacts/{run_id}/preview`
- `GET /artifacts/{run_id}/log`
- `GET /artifacts/{run_id}/report-assets/{asset_path}`

Additional UI routes are implemented under `/ui/...` for dashboard forms and service controls.

## 9. Software Dependencies

Runtime dependencies from `pyproject.toml`:

- `affine>=2.4.0`
- `attrs>=25.4.0`
- `click>=8.3.1`
- `matplotlib>=3.10.7`
- `numpy>=2.3.5,<2.4`
- `packaging>=25.0`
- `pillow>=12.0.0`
- `PyYAML>=6.0.3`
- `rasterio>=1.4.3`
- `requests>=2.32.5`
- `fastapi>=0.115.0`
- `uvicorn>=0.30.0`
- `jinja2>=3.1.0`
- `python-multipart>=0.0.9`
- `pydantic>=2.8.0`

Development dependencies:

- `pytest>=8.0`
- `pytest-cov>=5.0`
- `httpx>=0.27,<1.0`
- `ruff>=0.6.0`
- `black>=24.0.0`

Third-party tools/services:

- Docker and Docker Compose plugin.
- OpenDroneMap Docker image.
- Optional sibling OpenAgri Weather, Irrigation Management, and Pest & Disease service repositories.

## 10. Testing and Validation (optional)

Testing strategy:

- Unit tests under `tests/unit/`.
- Integration tests under `tests/integration/`.
- System/smoke tests under `tests/system/`.

Recommended commands:

```bash
make test
python -m pytest tests/unit -q
python -m pytest tests/integration -q
python -m pytest tests/system -q
python -m pytest tests --cov=agrivision --cov-report=term-missing
```

Continuous Integration:

GitHub Actions workflow `.github/workflows/ci.yml` validates Python 3.11 and 3.12 installation, `make lint`, tests with coverage, `make smoke-config`, `docker compose -f docker-compose.yml config`, and Dockerfile buildability.

Known test coverage:

To be confirmed. CI generates a terminal coverage report, but no fixed coverage percentage is documented.

## 11. Performance and Scalability (optional)

Performance benchmarks: To be confirmed. No benchmark results are documented.

Scalability limits:

- ODM is CPU, memory, and disk intensive.
- Windows self-hosting guidance recommends `AGRIVISION_MAX_ACTIVE_ODM_RUNS=1`.
- Windows host guidance recommends 32 GB RAM for ODM workloads, at least 100 GB free disk space for active projects, and Docker Desktop memory of 16 GB minimum / 24 GB or more recommended.
- Deployment settings include `AGRIVISION_MIN_FREE_DISK_GB` and `AGRIVISION_MAX_ACTIVE_ODM_RUNS`.

## 12. Security Considerations

Authentication/authorization:

- The local dashboard has no built-in public authentication documented.
- For public/self-hosted exposure, documentation requires Cloudflare Access or equivalent external login before sharing the dashboard URL.
- External OpenAgri service credentials are supplied through `.env` or environment variables.

Data protection:

- Secrets are not intended to be stored in `config.yaml`.
- Dashboard responses mask credentials and do not return full credential values to the browser.
- `.env` must not be committed with real credentials.

Known vulnerabilities:

To be confirmed. No vulnerability assessment, SBOM, or dependency audit result is documented.

## 13. Licensing and Usage Rights

Chosen open source license: European Union Public Licence (EUPL) v1.2, based on OpenAgri D2.5 guidance and repository metadata.

Attribution requirements: Follow EUPL v1.2 requirements.

Commercial use permissions: To be confirmed with the final license and project owner.

License note:

OpenAgri D2.5 confirms EUPL v1.2 as the default project license strategy for reusable open-source software services. Repository license metadata has been aligned to EUPL v1.2.

## 14. Contribution Guidelines

How to contribute:

No dedicated `CONTRIBUTING.md` is present. README guidance says to follow the existing style, keep secrets out of config and commits, run `make lint` and `make test`, and update documentation when behavior or commands change.

Coding standards:

- Ruff linting with selected `E`, `F`, and `I` rules.
- Black formatting with line length 88.
- Existing Python package/module organization should be preserved.

Issue tracking:

GitHub issue templates exist for bug reports, feature requests, and support requests under `.github/ISSUE_TEMPLATE/`.

Code review process:

To be confirmed. No formal review policy is documented.

## 15. Versioning and Changelog (optional)

Versioning scheme:

- `pyproject.toml` version is `1.0.0`.
- `docs/developer/release.md` recommends semantic version tags such as `v1.0.0`.

Changelog:

To be confirmed. No `CHANGELOG.md` or release notes file is present.

## 16. Roadmap and Future Work

Planned features and improvements:

- `docs/architecture/interoperability.md` notes future hardening of provisional OpenAgri/OCSM JSON-LD terms once target vocabulary classes/properties are fixed.
- The same document describes a possible optional adapter to send package manifests or JSON-LD payloads to an OpenAgri Reporting Service and store the returned report artifact.
- ARM/Raspberry Pi deployment is identified as a target profile but not yet validated.

## 17. Known Limitations

- Public dashboard access must be protected externally; built-in authentication is not documented.
- ODM stages require Docker and Docker socket access in the Compose flow.
- External service enrichment depends on configured Weather, Irrigation, and PDM services and credentials.
- ARM/Raspberry Pi deployment is not validated.
- Benchmark and fixed coverage figures are not documented.
- Citation format, commercial reuse permission, and role labels are not fully confirmed.

## 18. Citation and Acknowledgements (optional)

Recommended citation format: To be confirmed. Suggested draft for owner review: `Fakidaris, N., & Evangelou, G. (2026). AgriVision Pipeline, version 1.0.0. Aigaio Skytech / OpenAgri. https://github.com/GEvang/agrivision-pipeline`

Funding acknowledgements: `This project has received funding from the European Union's Horizon Europe research and innovation programme under grant agreement No 101134083.`

## 19. Contact and Support

Maintainer name: Nektarios Fakidaris, Giannis Evangelou. Giannis Evangelou is the software engineer; Nektarios Fakidaris's exact project role should be confirmed.

Institution: Aigaio Skytech

Support email/Raising issues: Primary: `nekfakidaris@gmail.com`; secondary/software engineering contact: `gevang97@outlook.com`; GitHub issue templates are present under `.github/ISSUE_TEMPLATE/`.

## Questions for John

1. Is commercial reuse permitted under the final selected software license?
2. What official software citation format should be used?
3. What exact role/title should be listed for Nektarios Fakidaris?
4. What code review/contribution process should be documented?
5. Are there benchmark results, target dataset sizes, or operational performance limits beyond the Windows/ODM guidance already documented?
