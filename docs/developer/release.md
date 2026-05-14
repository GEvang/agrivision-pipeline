# Release flow

1. Run lint and tests.
2. Build the Docker image.
3. Zip the repository or publish the image.

## License decision note

The repository currently uses the MIT license. This is permissive and compatible with open-source reuse, but it differs from the EUPL 1.2 baseline described for OpenAgri core services.

Before a formal OpenAgri release, confirm whether AgriVision should:

1. remain MIT as an ADS-level integration project;
2. switch to EUPL 1.2 for closer OpenAgri alignment; or
3. dual-license if downstream reuse requires both permissive and EU-aligned licensing terms.

Any license change should be reviewed by the project owner before release because it affects contribution and redistribution terms.

## Versioning checklist

- Tag source releases with semantic versions such as `v0.2.0`.
- Tag Docker images with the same version where images are published.
- Keep `pyproject.toml` version, Docker image tag, and release notes aligned.
- Record known platform support, including whether the release was validated on Windows Docker Desktop, Linux x86_64, and ARM/edge targets.
