# Run AgriVision Pipeline

## Canonical operator commands

Diagnostics:

```bash
python run.py --doctor
```

CLI pipeline run:

```bash
python run.py
```

Dashboard:

```bash
python run.py --serve-dashboard --host 127.0.0.1 --port 8008
```

Then open `http://127.0.0.1:8008`.

## Where outputs live

- reports and generated artifacts under `output/`
- run metadata and logs under `runtime/runs/`
- previews under `runtime/runs/<run_id>/previews/`
