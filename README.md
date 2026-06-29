# AgriVision Pipeline

AgriVision is a dashboard-first drone imagery workflow for orthophotos, vegetation analysis, field reports, and optional OpenAgri service integrations.

The simplest way to start it is:

```bash
git clone https://github.com/GEvang/agrivision-pipeline.git
cd agrivision-pipeline
docker compose up --build -d
```

Then open:

- [http://127.0.0.1:8008](http://127.0.0.1:8008)

The dashboard starts even if `.env` is missing and even if optional services are not installed yet.

## Quick Start

### Windows

1. Install Docker Desktop.
2. Clone or download AgriVision.
3. Double-click [Start AgriVision Windows.bat](D:\Jobs\Aigaio Skytech\OpenAgri\OpenAgri_Repository\agrivision-pipeline\Start AgriVision Windows.bat).
4. Your browser opens at [http://127.0.0.1:8008](http://127.0.0.1:8008).

### Linux

1. Install Docker.
2. Clone AgriVision.
3. Run:

```bash
chmod +x "Start AgriVision Linux.sh"
./"Start AgriVision Linux.sh"
```

4. Open [http://127.0.0.1:8008](http://127.0.0.1:8008).

### macOS

1. Install Docker Desktop.
2. Clone or download AgriVision.
3. Run once:

```bash
chmod +x "Start AgriVision macOS.command"
```

4. Double-click [Start AgriVision macOS.command](D:\Jobs\Aigaio Skytech\OpenAgri\OpenAgri_Repository\agrivision-pipeline\Start AgriVision macOS.command).
5. Your browser opens at [http://127.0.0.1:8008](http://127.0.0.1:8008).

## Universal Terminal Command

```bash
git clone https://github.com/GEvang/agrivision-pipeline.git
cd agrivision-pipeline
docker compose up --build -d
```

Then open:

- [http://127.0.0.1:8008](http://127.0.0.1:8008)

## What Works On First Launch

- The dashboard and API
- Uploads
- Run tracking
- Reports and exported run packages
- Runtime folder creation
- Default dashboard-managed settings in `runtime/settings.json`

These do **not** need to exist before the dashboard opens:

- `.env`
- OpenAgri Weather Service
- OpenAgri Irrigation Management
- OpenAgri Pest & Disease Management
- API keys
- Drone images
- Docker socket access inside the dashboard container

## Optional Services

The Settings page shows whether optional services are:

- Installed or Not installed
- Connected or Not connected
- Available or Not tested for OpenDroneMap

Missing optional services are shown as dashboard warnings, not startup errors.

## Persistent Folders

The base Docker setup keeps data in these local folders:

- `./data`
- `./output`
- `./runtime`

Important runtime locations:

- uploaded datasets: `data/uploads/<upload_id>/`
- run metadata and logs: `runtime/runs/<run_id>/`
- dashboard settings: `runtime/settings.json`
- saved reports and orthophotos: `output/runs/<run_id>/`
- exported run packages: `runtime/exports/`

## Running Without Docker

Docker is the recommended dashboard startup path.

Python virtualenv setup is still supported for developers and advanced operators, but it is no longer required just to open the dashboard. See:

- [docs/operator/install.md](D:\Jobs\Aigaio Skytech\OpenAgri\OpenAgri_Repository\agrivision-pipeline\docs\operator\install.md)
- [docs/operator/run.md](D:\Jobs\Aigaio Skytech\OpenAgri\OpenAgri_Repository\agrivision-pipeline\docs\operator\run.md)
- [docs/developer/local-dev.md](D:\Jobs\Aigaio Skytech\OpenAgri\OpenAgri_Repository\agrivision-pipeline\docs\developer\local-dev.md)

## API Docs

When the dashboard is running:

- OpenAPI JSON: [http://127.0.0.1:8008/openapi.json](http://127.0.0.1:8008/openapi.json)
- Swagger UI: [http://127.0.0.1:8008/docs](http://127.0.0.1:8008/docs)
- ReDoc: [http://127.0.0.1:8008/redoc](http://127.0.0.1:8008/redoc)

## OpenAgri Alignment

AgriVision is designed as an OpenAgri-aligned Agricultural Digital Solution. It can integrate with OpenAgri Weather, Irrigation, and Pest & Disease services when those are installed and configured, but the dashboard can start independently with safe defaults.
