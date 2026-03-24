# Running AgriVision

## CLI

```bash
python run.py --doctor
python run.py --run-resize
python run.py --skip-odm
python run.py --skip-weather
python run.py --skip-report
```

## Dashboard

```bash
uvicorn agrivision.app.api:app --host 127.0.0.1 --port 8008
```

Then open the dashboard in your browser and use:

1. **New Run** to upload a dataset and select processing steps
2. **Dashboard** to review recent runs
3. **Run Detail** to inspect logs, reports, and orthophoto previews
4. **Settings** to update non-secret config and replace credentials

## Notes

The first dashboard version keeps storage lightweight and filesystem-backed. Uploaded datasets are staged into the existing pipeline input location before execution so the current pipeline flow remains intact.
