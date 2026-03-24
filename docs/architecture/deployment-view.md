# Deployment view

## Canonical operational surface

AgriVision Pipeline exposes one operator-facing deployment surface at the repository root:

- `install_agrivision.sh`
- `run.py`
- `Dockerfile`
- `docker-compose.yml`
- `docker-entrypoint.sh`

## Supporting material

The `deployment/` directory now exists only for supplementary examples or internal helper content. It is not a second installation or runtime path.

## Runtime contexts

AgriVision supports:

- local Python execution;
- containerized execution with project volume mounting; and
- edge-oriented configuration profiles through dedicated config variants.
