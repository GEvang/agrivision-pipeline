# Local development

## Editable install

```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install -e ".[dev]"
cp .env.example .env
```

Python 3.11 and 3.12 are the supported development runtimes in CI. The package metadata requires Python `>=3.11`.

## Raw dashboard server

For development only, you can run the FastAPI app directly:

```bash
uvicorn agrivision.app.api:app --host 127.0.0.1 --port 8008 --reload
```

The canonical operator dashboard command remains:

```bash
python run.py --serve-dashboard --host 127.0.0.1 --port 8008
```
