# Run AgriVision

## Recommended startup

```bash
docker compose up --build -d
```

Then open:

- `http://127.0.0.1:8008`

## Launcher shortcuts

- Windows: `Start AgriVision Windows.bat`
- Linux: `Start AgriVision Linux.sh`
- macOS: `Start AgriVision macOS.command`

## First launch behavior

- the dashboard creates `runtime/settings.json` if it does not exist
- missing optional services appear in Settings as `Not installed` or `Not connected`
- the Weather settings form only requires an OpenWeather API key when Weather enrichment is needed
- missing `.env` does not block startup

## Where outputs live

- reports and generated artifacts: `output/`
- saved per-run outputs: `output/runs/<run_id>/`
- run metadata and logs: `runtime/runs/<run_id>/`
- previews: `runtime/runs/<run_id>/previews/`
- exports: `runtime/exports/`

## Advanced commands

For CLI pipeline work, testing, or service bootstrap helpers, use the commands documented in:

- `README.md`
- `docs/developer/local-dev.md`
- `docs/developer/testing.md`
