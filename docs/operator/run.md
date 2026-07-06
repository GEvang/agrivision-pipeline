# Run AgriVision

This page covers normal operator use after installation.

## Start

```bash
docker compose up --build -d
```

Open `http://127.0.0.1:8008`.

## Stop

```bash
docker compose down
```

This stops the dashboard container but leaves `data/`, `output/`, and `runtime/` intact.

## Daily Workflow

1. Open the dashboard.
2. Upload imagery or import an existing orthophoto set.
3. Create a run and choose the required steps.
4. Wait for run completion or inspect the run detail page if it fails.
5. Download reports, orthophotos, or the export package.

## What You Should Expect

- `runtime/settings.json` is created on first launch if missing
- missing companion services show up as warnings in Settings
- weather credentials are only needed if you actually enable weather enrichment
- the base dashboard can run without `.env`

## Output Locations

- reports and generated artifacts: `output/`
- per-run saved outputs: `output/runs/<run_id>/`
- run metadata and logs: `runtime/runs/<run_id>/`
- previews: `runtime/runs/<run_id>/previews/`
- export packages: `runtime/exports/`

## Useful Operator References

- install and first-run setup: `docs/operator/install.md`
- failure recovery: `docs/operator/troubleshooting.md`
- offline and constrained environments: `docs/operator/offline-edge.md`
