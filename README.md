# AgriVision Pipeline

AgriVision Pipeline is an OpenAgri-aligned drone imagery pipeline with two supported operator interfaces that share the same processing core:

- **CLI** for direct pipeline execution
- **Dashboard** for uploads, run tracking, reports, previews, and settings

The core remains transport-agnostic. `agrivision/domain/`, `agrivision/pipeline/`, `agrivision/services/`, and `agrivision/integrations/` continue to own business logic and integrations. The web layer under `agrivision/app/` stays thin.

## Canonical operator install

```bash
git clone https://github.com/GEvang/agrivision-pipeline.git
cd agrivision-pipeline
./install_agrivision.sh
source .venv/bin/activate
python run.py --doctor
```

## Canonical operator run path

CLI:

```bash
python run.py
```

Dashboard:

```bash
python run.py --serve-dashboard --host 127.0.0.1 --port 8008 --host 127.0.0.1 --port 8008
```

Open `http://127.0.0.1:8008` in your browser.

## Configuration and secrets

- Keep **non-secret settings** in `config.yaml`
- Keep **secrets** in `.env` or exported environment variables
- Use `cp .env.example .env` as the starting point for local setup
- The dashboard masks secrets and does not return full credential values in responses

## Runtime storage

- `data/uploads/<upload_id>/` — uploaded image datasets
- `runtime/runs/<run_id>/params.json`
- `runtime/runs/<run_id>/status.json`
- `runtime/runs/<run_id>/outputs.json`
- `runtime/runs/<run_id>/run.log`
- `runtime/runs/<run_id>/previews/`

## Common commands

```bash
python run.py --doctor
python run.py --run-resize
python run.py --skip-odm
python run.py --skip-weather
python run.py --skip-report
python -m pytest -q
python -m ruff check .
```

## Docker

Root-level Docker assets are the only retained container path:

```bash
docker compose config
docker compose build
docker compose up
```

## Developer notes

Developer-oriented alternatives such as raw `uvicorn`, editable installs, and dev tooling are documented under `docs/developer/`.
