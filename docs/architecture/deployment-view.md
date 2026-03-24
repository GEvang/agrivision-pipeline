# Deployment view

## Canonical deployment assets

The canonical deployment bundle lives under `deployment/`.

- `deployment/docker/` — Dockerfile, compose file, and entrypoint
- `deployment/scripts/` — install, bootstrap, and cleanup helpers
- `deployment/examples/` — sample deployment notes

## Compatibility wrappers

The following root-level files are kept for operator convenience and backwards compatibility:

- `Dockerfile`
- `docker-compose.yml`
- `bootstrap.sh`
- `install_agrivision.sh`

They should be understood as wrappers around the same deployment path, not as a separate second deployment architecture.

## Runtime contexts

AgriVision supports:

- local Python execution;
- containerized execution with project volume mounting; and
- edge-oriented configuration profiles through dedicated config variants.
