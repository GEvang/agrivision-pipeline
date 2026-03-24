# Operator install

## Local host install

From the repository root:

```bash
./deployment/scripts/install.sh
source venv/bin/activate
python run.py --doctor
```

The installer prepares Python, Docker, required folders, ODM image pull, and optional Weather/Irrigation runtime reconciliation.

## Docker install and run

From the repository root:

```bash
docker compose -f deployment/docker/docker-compose.yml up --build
```

This path mounts the full repository into `/workspace`, uses `config.yaml` as the active config, and passes the host project root through `HOST_PROJECT_ROOT` for local sibling-service bootstrapping.
