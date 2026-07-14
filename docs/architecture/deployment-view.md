# Deployment view

AgriVision Pipeline exposes one public operational surface at the repository root: launchers, Dockerfile, compose file, and entrypoint.

The supported assets are:

- `Dockerfile`
- `docker-compose.yml`
- `docker-entrypoint.sh`
- `.env.example`
- `Start AgriVision Windows.bat`
- `Start AgriVision Linux.sh`
- `Start AgriVision macOS.command`

The Docker Compose service starts the dashboard with `python run.py --serve-dashboard --host 0.0.0.0 --port 8008`.

The current container layout is:

- working directory: `/app`
- code mount: `./agrivision:/app/agrivision`
- data mount: `./data:/app/data`
- output mount: `./output:/app/output`
- runtime mount: `./runtime:/app/runtime`
- Docker socket mount: `/var/run/docker.sock:/var/run/docker.sock`

This is not a full bind-mount of the repository. It is a selected-path runtime layout.
