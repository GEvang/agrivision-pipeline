# Deployment

The root-level operational assets are the only supported deployment surface:

- `install_agrivision.sh`
- `Dockerfile`
- `docker-compose.yml`
- `docker-entrypoint.sh`
- `.env.example`

## Root Docker flow

```bash
docker compose config
docker compose build
docker compose up
```

For local operator use, prefer the installer and `python run.py` commands documented in the README. Activate the project with `source .venv/bin/activate`.

The Compose service publishes the dashboard on port `8008`, mounts the repository at `/workspace`, and mounts `/var/run/docker.sock` so ODM stages can launch OpenDroneMap containers. If the Docker socket is unavailable, the dashboard can start but ODM stages will fail.

For Windows self-hosting through Cloudflare Tunnel, see `docs/operator/windows-self-hosting.md`.
