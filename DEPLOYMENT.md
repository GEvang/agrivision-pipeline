# AgriVision Deployment Guide

## Validated runtime model

AgriVision now supports one clean production-style runtime and one clean development runtime built on the same Docker foundation.

### Farmer/operator workflow (recommended)

Use Docker from the project root:

```bash
docker compose up --build agrivision
```

This workflow assumes:
- `config.yaml` is edited before the run
- drone imagery is already in `data/`
- sibling WeatherService and IrrigationManagement repos live under the same project root
- Docker is installed on the Linux machine

What happens during startup:
- AgriVision reads `config.yaml`
- sibling service `.env` files are regenerated deterministically from the current config
- changed service env values trigger container recreation
- unchanged healthy services are left running
- the AgriVision app container connects to the host Docker daemon for ODM
- outputs persist in `./output`

### Developer/container workflow

Use the same compose stack, but add validation commands:

```bash
docker compose up --build agrivision
docker compose run --rm agrivision python -m ruff check .
docker compose run --rm agrivision python -m pytest tests
docker compose run --rm agrivision make smoke-config
```

This is the preferred workflow for development because it uses the same Dockerized runtime model as operations.

## Why the Docker workflow now works end-to-end

The root app container now:
- installs the Docker CLI
- mounts `/var/run/docker.sock`
- runs with `network_mode: host` on Linux so `127.0.0.1` service URLs in `config.yaml` remain valid
- mounts the full project root into `/workspace`
- maps ODM bind mounts back to the host project path through `HOST_PROJECT_ROOT`

That closes the ODM runtime gap that previously prevented `docker compose up --build agrivision` from finishing.

## Config ownership

`config.yaml` is the source of truth for:
- AgriVision app behavior and paths
- Weather base URL, username, password, OpenWeather key
- Irrigation base URL, email, password, token, port/service directory

Derived runtime artifacts:
- `OpenAgri-WeatherService/.env`
- `OpenAgri-IrrigationManagement/.env`

If `config.yaml` changes, rerun the pipeline with Docker. AgriVision rewrites only the keys that changed and recreates the affected service when runtime drift is detected.

## Fresh machine setup

For a Docker-first machine:

1. Install Docker and Docker Compose plugin.
2. Place the project on disk.
3. Edit `config.yaml`.
4. Place input data under `data/`.
5. Run:

```bash
docker compose up --build agrivision
```

Optional host setup remains available:

```bash
bash install_agrivision.sh
source venv/bin/activate
```

## Rerun after config changes

1. Edit `config.yaml`
2. Rerun:

```bash
docker compose up --build agrivision
```

Expected outcome:
- changed Weather/Irrigation values update the sibling `.env`
- changed service env triggers `docker compose up -d --force-recreate` inside the sibling repo
- unchanged healthy services are not restarted
- weather runtime validation fails clearly if auth works but the weather data endpoint is unhealthy

## Reset / reinstall

Host reset path:

```bash
python cleanup.py --reset-install --reinstall
```

Container cleanup path:

```bash
docker compose down
```

## Verification checklist

### Configuration and code quality

```bash
make lint
make test
make smoke-config
```

### Dockerized validation

```bash
docker compose run --rm agrivision python -m ruff check .
docker compose run --rm agrivision python -m pytest tests
docker compose up --build agrivision
```

### Weather verification

After the run, confirm:
- the weather section is populated in the final report
- WeatherService no longer contains placeholder credentials in its `.env`
- the final report no longer shows `N/A` when the service and upstream key are valid

## Troubleshooting

### ODM fails with Docker-related errors

Check:
- Docker is installed on the host
- `/var/run/docker.sock` exists
- the root compose file still mounts the Docker socket
- `HOST_PROJECT_ROOT` points to the real host path of the project

### Weather still returns `N/A`

Check:
- `config.yaml` contains a real `weather.openweather_api_key`
- the sibling WeatherService `.env` was reconciled
- the protected endpoint returns data instead of 500
- the report notes include no weather runtime errors
