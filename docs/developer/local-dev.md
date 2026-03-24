# Local development

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install -e ".[dev]"
```

## Useful commands

```bash
python run.py --doctor
python run.py --cleanup
python -m agrivision.app.cli --doctor
python -m uvicorn agrivision.app.api:app --host 127.0.0.1 --port 8008
make lint
make test
make smoke-config
```

## Docker validation

```bash
docker compose -f docker-compose.yml config
docker build -f Dockerfile -t agrivision-pipeline:dev .
```
