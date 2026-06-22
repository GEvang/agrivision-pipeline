# Deployment view

AgriVision Pipeline exposes one public operational surface at the repository root: installer, Dockerfile, compose file, and entrypoint.

The supported assets are:

- `install_agrivision.sh`
- `Dockerfile`
- `docker-compose.yml`
- `docker-entrypoint.sh`
- `.env.example`

The Docker Compose service starts the dashboard with `python run.py --serve-dashboard --host 0.0.0.0 --port 8008`, bind-mounts the repository at `/workspace`, and mounts `/var/run/docker.sock` for ODM container launches.
