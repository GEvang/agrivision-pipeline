# Installation

## Local install

```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[dev]"
```

## Container-oriented install

Canonical deployment assets live in `deployment/docker/`.

```bash
docker compose -f deployment/docker/docker-compose.yml config
```

Use the root-level `install_agrivision.sh` wrapper only as a convenience entrypoint; it delegates to `deployment/scripts/install.sh`.

## Configuration

Copy the example profile and adjust paths and credentials:

```bash
cp config/config.example.yaml config.yaml
```

Prefer environment variables or `.env` for secrets.
