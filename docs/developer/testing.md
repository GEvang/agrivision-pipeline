# Testing

## Test suites

- `tests/unit/` — pure logic and helper behavior
- `tests/integration/` — cross-module integration checks
- `tests/system/` — CLI and end-to-end smoke checks

## Recommended commands

```bash
make test
python -m pytest tests/unit -q
python -m pytest tests/integration -q
python -m pytest tests/system -q
python -m pytest --cov=agrivision --cov-report=term-missing
```

## CI expectations

Continuous integration validates:

- linting;
- unit/integration/system tests;
- coverage reporting;
- compose-file validation; and
- Dockerfile buildability.
