# Release Flow

Use this checklist before tagging a release.

## Before Tagging

1. Run `make lint`.
2. Run `python -m pytest tests --cov=agrivision --cov-report=term-missing`.
3. Run `make smoke-config`.
4. Run `docker compose -f docker-compose.yml config`.
5. Run `docker build -f Dockerfile -t agrivision-release-check .`.

## Versioning Rules

- use semantic versions such as `v1.0.0`
- keep `pyproject.toml` version and application-reported version aligned
- if a published Docker image exists, tag it with the same release version

## Release Artifacts

At minimum, a release should identify:

- the git tag
- the matching source state
- the Docker image tag if one is published
- known validated platforms
- any major operator-facing changes

## Platform Validation To Record

- Windows Docker Desktop
- Linux x86_64
- ARM or edge hardware, if actually tested

Record only the platforms exercised for that release.
