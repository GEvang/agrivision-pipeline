# Deployment

AgriVision supports two operator deployment methods:

- the provided start files
- Docker Compose

## Start Files

- Windows: `Start AgriVision Windows.bat`
- Linux: `Start AgriVision Linux.sh`
- macOS: `Start AgriVision macOS.command`

The start files launch the dashboard and the host service helper, which clones, configures and starts the OpenAgri services. The Linux start file also runs the containers as your user, so `data/`, `output/`, `runtime/` and the service repos are not owned by root. Helper output goes to `runtime/service-helper/logs/helper.log`.

The OpenAgri services are cloned at commits pinned in AgriVision (`*_REPO_REF` in `agrivision/runtime/{weather,irrigation,pdm}.py`). Update a pin only after testing the new upstream version.

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

## Resetting

Reset only what you need; every level asks you to type `RESET` and refuses while a run is active. Stop the dashboard first for the `services` and `all` levels.

| Level | Removes | Keeps |
|---|---|---|
| `outputs` | runs, uploads, reports, exports | settings, credentials, services |
| `services` (optionally `--service weather\|irrigation\|pdm`) | the service's containers, Docker volumes (its database) and cloned folder | your runs and settings |
| `all` | both of the above, plus dashboard settings and saved credentials | Docker images |

Levels that delete runs offer to write a zip backup of runs, saved outputs and uploads first (`--backup PATH`, or `--no-backup`). Docker images stay unless you add `--remove-images`.

With Python on the host:

```bash
python run.py --reset outputs
```

With a Docker-only install, run it through the dashboard image from the project folder:

```bash
docker run --rm -it -v "$PWD:/workspace" -v /var/run/docker.sock:/var/run/docker.sock -w /workspace -e AGRIVISION_PROJECT_ROOT=/workspace -e AGRIVISION_CONFIG_PATH=/workspace/config.yaml -e AGRIVISION_RUNTIME_SETTINGS_PATH=/workspace/runtime/settings.json agrivision-pipeline:1.0.0 python run.py --reset services --service irrigation
```

## Required Services

Before field analysis, confirm these OpenAgri services are configured and reachable from the Settings page:

- Weather
- Irrigation
- Pest & Disease

## Internet Access

Do not publish port `8008` directly to the internet. Put AgriVision behind an external access layer such as Cloudflare Access, VPN, or an authenticated reverse proxy.
