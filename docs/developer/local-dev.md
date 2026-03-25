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

## Raw dashboard server

For development only, you can run the FastAPI app directly:

```bash
uvicorn agrivision.app.api:app --host 127.0.0.1 --port 8008 --reload
```
