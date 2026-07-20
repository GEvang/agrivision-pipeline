# Deployment View

AgriVision exposes the supported operator launch assets at the repository root.

The supported assets are:

- `Dockerfile`
- `docker-compose.yml`
- `docker-entrypoint.sh`
- `.env.example`
- `Start AgriVision Windows.bat`
- `Start AgriVision Linux.sh`
- `Start AgriVision macOS.command`

Docker Compose starts the dashboard with `python run.py --serve-dashboard --host 0.0.0.0 --port 8008`.

The current container layout is:

- working directory: `/app`
- code mount: `./agrivision:/app/agrivision`
- data mount: `./data:/app/data`
- output mount: `./output:/app/output`
- runtime mount: `./runtime:/app/runtime`
- Docker socket mount: `/var/run/docker.sock:/var/run/docker.sock`

This selected-path runtime layout keeps operator data in `data/`, `output/`, and `runtime/`.
