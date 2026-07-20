# Deployment

AgriVision supports two operator deployment methods:

- the provided start files
- Docker Compose

## Supported Root-Level Operational Assets

- `Dockerfile`
- `docker-compose.yml`
- `docker-entrypoint.sh`
- `.env.example`
- `Start AgriVision Windows.bat`
- `Start AgriVision Linux.sh`
- `Start AgriVision macOS.command`

## Standard Local Deployment

Use one of the provided start files when possible:

- Windows: `Start AgriVision Windows.bat`
- Linux: `Start AgriVision Linux.sh`
- macOS: `Start AgriVision macOS.command`

Or start with Docker Compose:

```bash
docker compose up --build -d
```

Then open `http://127.0.0.1:8008`.

Before field analysis, confirm the required OpenAgri Weather, Irrigation, and Pest & Disease services are configured and reachable from the Settings page.

## What the Compose Service Does

- publishes the dashboard on port `8008`
- mounts `./agrivision`, `./data`, `./output`, and `./runtime` into `/app`
- mounts `/var/run/docker.sock` so ODM jobs can launch Docker workloads
- writes runtime settings to `runtime/settings.json`

## Internet Access

For internet access, keep AgriVision behind an external access layer such as Cloudflare Access. Do not publish port `8008` directly to the internet.

For internet access from Windows or Linux hosts, use `docs/operator/internet-cloud-deployment.md`.
