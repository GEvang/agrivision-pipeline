# Contributing

## Before Opening A Change

- keep changes scoped
- do not commit real credentials or populated `.env` files
- update documentation when behavior, commands, or operator expectations change

## Development Setup

Use `docs/developer/local-dev.md` for local setup and `docs/developer/testing.md` for test commands.

## Minimum Quality Bar

Before opening a pull request or handing off a patch:

```bash
make lint
python -m pytest tests --cov=agrivision --cov-report=term-missing
make smoke-config
docker compose -f docker-compose.yml config
```

## Documentation Rules

- keep docs specific to the current repository behavior
- do not add placeholder sections, unresolved questionnaires, or template filler
- prefer one good guide over several overlapping ones

## Issues

Use the GitHub issue templates for:

- bug reports
- feature requests
- support questions
