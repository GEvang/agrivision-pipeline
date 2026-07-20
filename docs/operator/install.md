# Install AgriVision

Use one of the provided start files or Docker. These are the supported installation methods for operators.

## Prerequisites

- Docker Desktop on Windows or macOS, or Docker Engine on Linux
- enough disk space for imagery, ODM intermediates, and generated outputs
- enough RAM for ODM workloads if you will build orthophotos locally

## Default Install

Use one of the provided start files:

- Windows: `Start AgriVision Windows.bat`
- Linux: `Start AgriVision Linux.sh`
- macOS: `Start AgriVision macOS.command`

Linux and macOS launchers may need execute permission first:

```bash
chmod +x "Start AgriVision Linux.sh"
chmod +x "Start AgriVision macOS.command"
```

Or start with Docker:

```bash
docker compose up --build -d
```

Open `http://127.0.0.1:8008`.

## First Launch

Expected behavior:

- `runtime/settings.json` is created automatically
- the dashboard opens at `http://127.0.0.1:8008`
- the Settings page shows Docker and OpenAgri service status

Before running field analysis, configure and start the required OpenAgri Weather, Irrigation, and Pest & Disease services.

## Remote Access

- For internet access, use `docs/operator/internet-cloud-deployment.md`
- For Windows self-hosting details, use `docs/operator/windows-self-hosting.md`
