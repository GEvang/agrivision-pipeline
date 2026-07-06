# Local Development

Use this path when changing code. Operators should use the Docker flow instead.

## Supported Python Versions

CI validates Python 3.11 and 3.12. Package metadata requires `>=3.11`.

## Editable Install

Linux or macOS:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -e ".[dev]"
cp .env.example .env
```

Windows PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

## Run The App

Development server:

```bash
uvicorn agrivision.app.api:app --host 127.0.0.1 --port 8008 --reload
```

Operator-equivalent local command:

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

- `.env` is optional for basic dashboard startup
- `config.yaml` is for non-secret config
- companion services are optional and can be developed independently
