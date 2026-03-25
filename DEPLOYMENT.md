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
