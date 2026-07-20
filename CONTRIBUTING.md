# Contributing And Support

## Before Opening A Change

- keep changes scoped
- do not commit real credentials or populated `.env` files
- update documentation when behavior, commands, or operator expectations change

## Quality Checks

```bash
make lint
python -m pytest tests --cov=agrivision --cov-report=term-missing
make smoke-config
docker compose -f docker-compose.yml config
```

## Issue Types

Use GitHub issues for:

- bug reports
- feature requests
- documentation updates
- support questions
- testing issues

## Documentation Rules

- keep documentation specific to current repository behavior
- keep operator instructions limited to the provided start files and Docker
- document OpenAgri Weather, Irrigation, and Pest & Disease services as required
- prefer one focused guide over several overlapping guides
