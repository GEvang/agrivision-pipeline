# Deployment

Canonical deployment assets live under `deployment/`:

- Docker image and compose assets: `deployment/docker/`
- Bootstrap/install/cleanup scripts: `deployment/scripts/`
- Config variants: `config/`

## Supported profiles

1. **Standalone host execution** using the local Python environment.
2. **Docker-local execution** with Docker socket access for ODM.
3. **Docker execution with sibling OpenAgri services** mounted beside the repo root.
4. **Edge/offline execution** reusing existing artifacts and skipping unavailable stages.

## Canonical commands

From the repository root:

```bash
./deployment/scripts/install.sh
python run.py --doctor
docker compose -f deployment/docker/docker-compose.yml up --build
```

The Docker compose file expects to be launched from the repository root so `${PWD}` resolves to the host-side repo root for sibling service bootstrapping.
