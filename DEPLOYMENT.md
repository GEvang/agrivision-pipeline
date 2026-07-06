# Deployment

This repository supports one primary operator deployment path: the root Docker Compose stack.

## Supported Deployment Assets

- `Dockerfile`
- `docker-compose.yml`
- `docker-entrypoint.sh`
- `.env.example`
- `Start AgriVision Windows.bat`
- `Start AgriVision Linux.sh`
- `Start AgriVision macOS.command`

## Standard Local Deployment

```bash
docker compose up --build -d
```

Then open `http://127.0.0.1:8008`.

Base startup does not require `.env` and does not require the optional OpenAgri services to be installed first.

## What the Compose Service Does

- publishes the dashboard on port `8008`
- mounts `./agrivision`, `./data`, `./output`, and `./runtime` into `/app`
- mounts `/var/run/docker.sock` so ODM jobs can launch Docker workloads
- writes runtime settings to `runtime/settings.json`

## When Not To Use This Flow

Do not treat the root Compose file as a hardened internet-facing deployment. It is for local use, trusted internal use, and Windows self-hosting behind external access protection.

For public or semi-public Windows exposure, use `docs/operator/windows-self-hosting.md`.

For local Python development instead of the operator deployment path, use `docs/developer/local-dev.md`.
