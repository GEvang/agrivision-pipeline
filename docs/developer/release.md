# Release flow

1. Run lint and tests.
2. Build the Docker image.
3. Zip the repository or publish the image.

## License note

The repository uses the European Union Public Licence (EUPL) v1.2 for OpenAgri alignment.

## Versioning checklist

- Tag source releases with semantic versions such as `v1.0.0`.
- Tag Docker images with the same version where images are published.
- Keep `pyproject.toml` version, Docker image tag, and release notes aligned.
- Record known platform support, including whether the release was validated on Windows Docker Desktop, Linux x86_64, and ARM/edge targets.
