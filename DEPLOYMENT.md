# Deployment

AgriVision supports two operator deployment methods:

- the provided start files
- Docker Compose

## Start Files

- Windows: `Start AgriVision Windows.bat`
- Linux: `Start AgriVision Linux.sh`
- macOS: `Start AgriVision macOS.command`

The start files launch the dashboard and the host service helper, which clones, configures and starts the OpenAgri services. The Linux start file also runs the containers as your user, so `data/`, `output/`, `runtime/` and the service repos are not owned by root. Helper output goes to `runtime/service-helper/logs/helper.log`.

The OpenAgri services are cloned at commits pinned in AgriVision (`*_REPO_REF` in `agrivision/services/{weather,irrigation,pdm}`). Update a pin only after testing the new upstream version.

## Docker Compose

```bash
docker compose up --build -d
```

On Linux with a standard Docker daemon, run Compose as your user so bind-mounted files stay yours:

```bash
AGRIVISION_UID=$(id -u) AGRIVISION_GID=$(id -g) AGRIVISION_DOCKER_GID=$(stat -c %g /var/run/docker.sock) docker compose up --build -d
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
