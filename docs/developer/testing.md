# Testing

## Test Suites

- `tests/unit/`: pure logic and helper behavior
- `tests/integration/`: cross-module integration checks
- `tests/system/`: CLI and end-to-end smoke checks

## Recommended Commands

```bash
make test
python -m pytest tests/unit -q
python -m pytest tests/integration -q
python -m pytest tests/system -q
python -m pytest tests --cov=agrivision --cov-report=term-missing
```

## CI Expectations

Continuous integration validates:

- Python 3.11 and 3.12 installation;
- `make lint`;
- `python -m pytest tests --cov=agrivision --cov-report=term-missing`;
- `make smoke-config`;
- `docker compose -f docker-compose.yml config`; and
- `docker build -f Dockerfile -t agrivision-ci-root .`.
