# Deployment

AgriVision supports two operator deployment methods:

- the provided start files
- Docker Compose

## Start Files

- Windows: `Start AgriVision Windows.bat`
- Linux: `Start AgriVision Linux.sh`
- macOS: `Start AgriVision macOS.command`

Linux and macOS launchers may need execute permission first:

```bash
chmod +x "Start AgriVision Linux.sh"
chmod +x "Start AgriVision macOS.command"
```

## Docker Compose

```bash
docker compose up --build -d
```

Open:

```text
http://127.0.0.1:8008
```

## Runtime Layout

The Compose service:

- publishes the dashboard on port `8008`
- mounts `./data`, `./output`, and `./runtime` for persistent operator data
- mounts `/var/run/docker.sock` so ODM jobs can launch Docker workloads
- writes runtime settings to `runtime/settings.json`

## Required Services

Before field analysis, confirm these OpenAgri services are configured and reachable from the Settings page:

- Weather
- Irrigation
- Pest & Disease

## Internet Access

Do not publish port `8008` directly to the internet. Put AgriVision behind an external access layer such as Cloudflare Access, VPN, or an authenticated reverse proxy.
