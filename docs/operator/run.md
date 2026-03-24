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

Dashboard run:

```bash
python run.py --serve-dashboard --host 127.0.0.1 --port 8008
```

## Dashboard flow

1. Open the dashboard in your browser.
2. Use **New Run** to upload a dataset.
3. Select the processing steps for that run.
4. Launch the run and monitor status.
5. Review reports, logs, and orthophoto previews.
6. Use **Settings** for non-secret config and masked credential updates.

## Notes

- `python run.py` remains the primary user-facing command surface.
- Raw `uvicorn` remains available for development but is not the main operator path.
- The dashboard continues to use lightweight filesystem-backed storage.
