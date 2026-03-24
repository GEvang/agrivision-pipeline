# Local development

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[dev]"
```

## Daily checks

```bash
make lint
make test
make smoke-config
python -m pytest --cov=agrivision --cov-report=term-missing
```

## Useful commands

```bash
python run.py --doctor
python run.py --cleanup
python -m agrivision.app.cli --doctor
```
