PYTHON ?= python
PIP ?= pip
RUFF ?= ruff
PYTEST ?= pytest

PYTHON ?= python

.PHONY: install install-dev lint format test smoke-config run serve-dashboard verify-phase5

install:
	./install_agrivision.sh

install-dev:
	$(PYTHON) -m pip install -r requirements.txt
	$(PYTHON) -m pip install -e ".[dev]"

lint:
	$(PYTHON) -m ruff check .

format:
	$(PYTHON) -m black .

test:
	$(PYTHON) -m pytest tests

smoke-config:
	$(PYTHON) -c "from agrivision.config.settings import load_config; load_config(); print('config smoke check passed')"

verify-phase5:
	$(PYTHON) -m pytest tests
	$(PYTHON) -m ruff check .

run:
	$(PYTHON) run.py

serve-dashboard:
	$(PYTHON) run.py --serve-dashboard --host 127.0.0.1 --port 8008
