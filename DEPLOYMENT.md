# Deployment

Canonical deployment assets now live under `deployment/`:

- Dockerfiles and compose assets: `deployment/docker/`
- Bootstrap/install/cleanup scripts: `deployment/scripts/`
- Config variants: `config/`

Recommended profiles:

1. Standalone host execution.
2. Docker-local execution with Docker socket access for ODM.
3. Docker execution with sibling OpenAgri services.
4. Edge/offline execution reusing existing artifacts.
