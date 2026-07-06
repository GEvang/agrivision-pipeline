# Install AgriVision

Use the Docker-based dashboard flow unless you are developing locally.

## Prerequisites

- Docker Desktop on Windows or macOS, or Docker Engine on Linux
- enough disk space for imagery, ODM intermediates, and generated outputs
- enough RAM for ODM workloads if you will build orthophotos locally

## Default Install

```bash
git clone https://github.com/GEvang/agrivision-pipeline.git
cd agrivision-pipeline
docker compose up --build -d
```

Open `http://127.0.0.1:8008`.

## OS Launchers

If you prefer launcher scripts instead of the raw Compose command:

- Windows: `Start AgriVision Windows.bat`
- Linux: `Start AgriVision Linux.sh`
- macOS: `Start AgriVision macOS.command`

Linux and macOS launchers may need execute permission first:

```bash
chmod +x "Start AgriVision Linux.sh"
chmod +x "Start AgriVision macOS.command"
```

## First Launch

Expected behavior:

- `runtime/settings.json` is created automatically
- the dashboard opens even if `.env` is missing
- missing OpenAgri companion services appear as warnings, not fatal startup errors

## When To Use Something Else

- For local Python development, use `docs/developer/local-dev.md`
- For Windows self-hosting behind Cloudflare, use `docs/operator/windows-self-hosting.md`
