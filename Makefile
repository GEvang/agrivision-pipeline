PYTHON ?= python

.PHONY: install install-dev lint format test smoke-config run

install:
	$(PYTHON) -m pip install -r requirements.txt

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
	$(PYTHON) -c "import run; run.load_local_env(); from agrivision.utils.settings import load_config; load_config(); print('config smoke check passed')"

run:
	$(PYTHON) run.py
