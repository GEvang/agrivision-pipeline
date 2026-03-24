# AgriVision Pipeline

AgriVision Pipeline is an operator-friendly drone imagery workflow with two supported runtime surfaces built on the same processing core:

- **CLI mode** for local or scripted execution
- **FastAPI dashboard** for uploads, run tracking, reports, previews, and settings

The transport-agnostic core remains in `agrivision/domain`, `agrivision/pipeline`, `agrivision/services`, and `agrivision/integrations`. The dashboard stays a thin adapter under `agrivision/app/`.

## Canonical operator workflow

### 1. Clone the repository

```bash
git clone https://github.com/GEvang/agrivision-pipeline.git
cd agrivision-pipeline
```

### 2. Run the installer

```bash
./install_agrivision.sh
```

### 3. Activate the environment

```bash
source .venv/bin/activate
```

### 4. Verify the setup

```bash
python run.py --doctor
```

### 5. Run AgriVision Pipeline

CLI pipeline run:

```bash
python run.py
```

Dashboard run:

```bash
python run.py --serve-dashboard --host 127.0.0.1 --port 8008
```

Then open `http://127.0.0.1:8008` in your browser.

## Secrets and configuration

- `config.yaml` is for **non-secret runtime settings** such as paths, location, base URLs, and processing options.
- `.env` or exported environment variables are for **secrets only**.
- `.env.example` shows the expected secret keys.
- Legacy YAML secret values are still read for compatibility, but the preferred path is `.env`.

Typical setup:

```bash
cp .env.example .env
```

Fill in only the credentials you actually use.

## Where AgriVision stores runtime data

- `data/uploads/<upload_id>/` — uploaded image datasets
- `runtime/runs/<run_id>/` — run metadata, logs, previews, outputs
- `output/` — reports, NDVI artifacts, irrigation output, weather output

## Dashboard pages

- `/` — dashboard with recent runs and latest outputs
- `/runs/new` — upload images and launch a run
- `/runs/{run_id}` — run detail, logs, artifacts, preview
- `/reports` — report history
- `/settings` — non-secret settings, masked credentials, diagnostics

## Developer notes

Operator docs now standardize on `install_agrivision.sh` and `python run.py`. Lower-level developer workflows such as raw `uvicorn`, direct editable installs, and Make targets remain available in `docs/developer/`.

## Verification commands

```bash
make lint
make test
make smoke-config
python -m pytest tests/system/test_dashboard_ui_smoke.py
python -m pytest tests/system/test_cli_doctor.py
```
