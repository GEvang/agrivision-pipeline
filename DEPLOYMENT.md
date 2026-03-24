# Deployment notes

## Canonical operational assets

The root-level assets are the supported operator-facing deployment surface:

- `install_agrivision.sh`
- `run.py`
- `Dockerfile`
- `docker-compose.yml`
- `docker-entrypoint.sh`

## Internal deployment material

The remaining `deployment/` directory is for supplementary examples and helper material only. It is not a second canonical deployment path.

## Canonical container validation

```bash
docker compose -f docker-compose.yml config
docker build -f Dockerfile -t agrivision-pipeline:local .
```
