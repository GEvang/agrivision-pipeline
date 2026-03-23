# AgriVision

AgriVision is a drone-imagery pipeline that produces orthophotos, vegetation analysis, grid-based crop-health summaries, and a farmer-ready HTML report.

## Supported runtime modes

- **Farmer/operator workflow (recommended):** run the full pipeline with Docker from the project root.
- **Developer/container workflow:** use the same Docker runtime, plus lint, tests, and smoke checks inside the same deployment model.
- **Local host workflow:** still available for troubleshooting with `source venv/bin/activate && python run.py`.

`config.yaml` is the source of truth for:
- AgriVision paths and pipeline behavior
- Weather credentials and OpenWeather API key
- Irrigation credentials and service settings

AgriVision reconciles the sibling service `.env` files from `config.yaml` and recreates the affected service containers when drift is detected.

## Farmer/operator quick start

1. Put your drone images under `data/images_full/rgb` and `data/images_full/mapir` as needed.
2. Edit `config.yaml` with your credentials and site settings.
3. Run the pipeline:

```bash

docker compose up --build agrivision
```

4. Open the generated report under `output/`.

## Developer/container workflow

Run the pipeline:

```bash

docker compose up --build agrivision
```

Run lint and tests in the same container runtime:

```bash

docker compose run --rm agrivision python -m ruff check .
docker compose run --rm agrivision python -m pytest tests
```

## Local host workflow

```bash
bash install_agrivision.sh
source venv/bin/activate
python run.py
```

## Reset / reinstall

```bash
python cleanup.py --reset-install --reinstall
```

## Verification

```bash
make lint
make test
make smoke-config
```

For the full deployment guide, validated Docker workflow, service reconciliation behavior, and troubleshooting notes, see [DEPLOYMENT.md](DEPLOYMENT.md).
