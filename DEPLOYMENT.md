# Deployment notes

The canonical deployment assets for AgriVision live under `deployment/`.

## Canonical paths

- `deployment/docker/Dockerfile`
- `deployment/docker/docker-compose.yml`
- `deployment/docker/entrypoint.sh`
- `deployment/scripts/install.sh`
- `deployment/scripts/bootstrap.sh`
- `deployment/scripts/cleanup.sh`

## Compatibility wrappers

The root-level `Dockerfile`, `docker-compose.yml`, `bootstrap.sh`, `docker-entrypoint.sh`, and `install_agrivision.sh` are maintained as thin compatibility wrappers so existing operator commands continue to work.

When updating deployment behavior, modify the canonical assets first and keep wrappers aligned.
