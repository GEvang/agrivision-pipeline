# Maintainer Notes

This page is for maintainers changing AgriVision code. It is not an operator installation method. Operators should use the provided start files or Docker as described in `docs/operator/install.md`.

## Supported Python Versions

CI validates Python 3.11 and 3.12. Package metadata requires `>=3.11`.

## Run The App For Code Changes

Maintainers can run the dashboard directly while changing code:

```bash
uvicorn agrivision.app.api:app --host 127.0.0.1 --port 8008 --reload
```

The operator-equivalent command is:

```bash
python run.py --serve-dashboard --host 127.0.0.1 --port 8008
```

## Common Developer Commands

```bash
python run.py --doctor
make lint
make test
python -m pytest tests/unit -q
python -m pytest tests/integration -q
python -m pytest tests/system -q
```

## Notes

- `config.yaml` is for non-secret config
- secrets belong in `.env` or host environment variables
- OpenAgri Weather, Irrigation, and Pest & Disease services are required for complete field analysis
